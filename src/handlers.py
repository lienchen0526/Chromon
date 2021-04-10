from typing import Dict, Generic, Literal, Optional, Tuple, Union
import chromeevents as Events
import chrometypes as Types
import json
import asyncio
import copy
from urllib.parse import urlparse
from core import ChromeBridge, Logger

class Handler(object):
    """
    Metaclass of all handlers. Each handler should only handle 'one' type of event. For example: Target.targetCreated
    The metaclss will assign event to proper sub-class handler.
    """

    cmd_lock = asyncio.Lock()
    trgt_session_lock = asyncio.Lock()

    _subhandlers: Dict[str, type] = {}
    _activedevent: Dict[str, int] = {}
    _pending_command: Dict[int, Tuple[type, Types.Generic.DebugCommand]] = {}
    _target_session: Dict[Types.Target.TargetID, Union[Types.Target.SessionID, Literal["Pending"]]] = {}
    interface: ChromeBridge
    logger: Logger

    def __init_subclass__(cls, interested_event: str) -> None:
        cls.interested_event = interested_event
        if cls._INSTANCE:
            return super().__init_subclass__()
        cls._INSTANCE = cls()
        if _handler := (Handler._subhandlers.get(interested_event)):
            raise AttributeError(f"Attempting to register multiple handler on single type of event. Current Exsit Handler: {_handler.__class__}. Attempted adding Handler: {cls.__class__}")
        Handler._subhandlers[interested_event] = cls._INSTANCE
        Handler._activedevent[interested_event] = max(Handler._activedevent.values(), default = 0) + 1
        return super().__init_subclass__()
    
    def __init__(self, interface: ChromeBridge, logger: Logger) -> None:
        super().__init__()
        self.__class__.interface = interface
        self.__class__.logger = logger

    @classmethod
    async def dispatch(cls, msg: Union[Types.Generic.DebugReply, dict]) -> None:
        """Dispatch incomming message to proper handler
        Args:
            msg (Unioon[Types.Generic.DebugReply, Events.BaseEvenv]): the message that debuggee should reply
        """

        if event := (msg.get('method')):
            if not cls._subhandlers.get(event, None):
                print(f"[+ Dispatch Error] Handler for the event {event} are not implement yet")
                # raise NotImplementedError(f"[Dispatch Error] Handler for the event {event} are not implement yet")
                pass
            else:
                await cls._subhandlers.get(event).handle(msg)
            return None

        if mid := (msg.get('id')):
            async with cls.cmd_lock:
                command_origin_pair = cls._pending_command.pop(mid, None)
            if not command_origin_pair:
                return None
            await command_origin_pair[0].catchReply(command_origin_pair[1], msg)
            return None
        
        raise TypeError(f"[Dispatch Error] Handler does not recognize the message {msg}")

    async def sendCommand(self, command: Types.Generic.DebugCommand) -> int:
        """This method is an command interface for subhander to send command to debugee browser.
        This method are suggested to use `asyncio.create_task` for invoking based on performance
        
        Args:
            command (Types.Generic.DebugCommand): The command object to sending to
        Return:
            message_id (int): The unique identifier of the command channel
        """
        async with self.cmd_lock:
            message_id = max(self._pending_command.keys(), default = 0) + 1
            command['id'] = message_id
            self._pending_command[message_id] = (self, command)
            self.interface.sendObj(command)

        return message_id
    
    def logEvent(self, msg:str, origin: Optional[str] = None) -> None:
        event_id = Handler._activedevent.get(self.interested_event, None)
        assert event_id is not None

        if event_id < 0:
            return None

        if origin:
            if not isinstance(origin, str):
                raise TypeError(f"origin is not str, is {type(origin)}")
        if not isinstance(msg, str):
            raise TypeError(f"msg is not str, is {type(msg)}")
        
        origin = self.__class__.__name__ if not origin else origin
        origin = " - ".join([str(event_id), origin])

        self.logger.log(
            origin = self.__class__.__name__ if not origin else origin,
            event = msg
        )
        return None
    
    async def handle(self):
        """Event handle function. Due to it method may access parent class resource with synchronization issue.
        It should be designed as an asynchronous function. Once the meta class <Handler> resource are not as expected, it will
        return the control flow back to event loop
        """
        raise NotImplementedError("Metaclass not implement handle yet")
    
    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        """This is command handling function if the handler issue some command to debugee.
        Due to it may also access meta class <Handler> resource, it also designed as an a-
        synchronous method.
        """
        raise NotImplementedError("Metaclass not implement catchReply yet")

class TargetAttachedHandler(Handler, interested_event = "Target.attachedToTarget"):
    _INSTANCE = None
    def __init__(self) -> None:
        pass
    
    async def handle(self, msg: Events.Target.attachedToTarget) -> None:

        session_id = msg.get('params').get('sessionId')
        target_id = msg.get('params').get('targetInfo').get('targetId')
        url = msg.get('params').get('targetInfo').get('url')[:10]
        type_ = msg.get('params').get('targetInfo').get('type')

        async with super().trgt_session_lock:
            super()._target_session[target_id] = session_id

        well_msg = {
            "targetId": target_id,
            "sessionId": session_id
        }
        self.logEvent(
            msg = json.dumps(well_msg),
            origin = "[Target Attached]"
        )
        await self.initTarget(targetId = target_id)
        return None
    
    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply) -> None:
        return None

    async def initTarget(self, targetId: Types.Target.TargetID):
        async with self.trgt_session_lock:
            sessionid = self._target_session.get(targetId)
        if not sessionid:
            raise KeyError(f"{targetId} does not exists")
        
        while sessionid == "Pending":
            async with self.trgt_session_lock:
                sessionid = self._target_session.get(targetId)
            await asyncio.sleep(0)
        
        await self._setAutoAttach(
            sessionId = sessionid, 
            enable = False
        )
        await self._setDiscoverTargets(
            sessionId = sessionid
        )

    async def _setDiscoverTargets(self, sessionId: Types.Target.SessionID) -> None:
        """Set new attached target can discover new sub-target.

        Args:
            sessionId (Types.Target.SessionID): The sessionid of the given parent target
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Target.setDiscoverTargets",
            "sessionId": sessionId,
            "params": {
                "discover": True
            }
        }
        await self.sendCommand(command = _cmd)
        return None

    async def _setAutoAttach(self, sessionId: Types.Target.SessionID, enable: bool = False) -> None:
        """Set new attached target do not auto attach
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Target.setAutoAttach",
            "sessionId": sessionId,
            "params":{
                "autoAttach": enable,
                "waitForDebuggerOnStart": False,
                "flatten": True,
                "windowOpen": False
            }
        }
        await self.sendCommand(command = _cmd)
        return None

class TargetCreatedHandler(Handler, interested_event = "Target.targetCreated"):
    _INSTANCE = None
    def __init__(self) -> None:
        self.counter = 0
        pass

    async def handle(self, msg: Events.Target.targetCreated) -> None:
        """
        Known Issue: Multiple Creation of single target event will receive.
        """

        t: Types.Target.TargetInfo = msg.get('params').get('targetInfo')
        t["url"] = urlparse(url = t["url"])._asdict()

        if not t.get('attached'):
            if t.get('type') in Types.Target.ValidTypes:
                async with self.trgt_session_lock:
                    _pending = self._target_session.get(t.get("targetId"), None)
                if not _pending:
                    self.logEvent(
                        msg = json.dumps(t),
                        origin = "[New Target Created]"
                    )
                    await self._attachToTarget(t)
                else:
                    # There are same Target Creation in previous
                    pass
        return None

    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply) -> None:
        """It may not be called directly from human. It will be call by metaclass `Handler`
        Args:
            command (Types.Generic.DebugCommand): The command sent by the handler
            msg (Type.Generic.DebugReply): The reply for the `command`
        """

        # Register targetId for relative sessionId
        if command.get('method') == 'Target.attachToTarget':
            #print(f"[In {self.__class__}] Target Attach command successfully executed!")
            return None
        raise NotImplementedError(f"Lien Implement Error: Invalid (call return) pair: {(command, msg)}")

    async def _attachToTarget(self, t: Types.Target.TargetInfo) -> None:
        async with self.trgt_session_lock:
            self._target_session[t.get("targetId")] = "Pending"
        method = "Target.attachToTarget"
        params = {
            "targetId": t.get("targetId"),
            "flatten": True
        }
        _cmd: Types.Generic.DebugCommand = {
            "method": method,
            "params": params
        }
        await self.sendCommand(command = _cmd)
        return None

class targetInfoChangeHandler(Handler, interested_event = "Target.targetInfoChanged"):
    _INSTANCE = None

    def __init__(self) -> None:
        pass

    async def handle(self, msg: Events.Target.targetInfoChange) -> None:
        t = msg.get('params').get('targetInfo')
        sess_id = msg.get('sessionId', None)
        async with self.trgt_session_lock:
            sess_id = self._target_session.get(t.get("targetId"), None)
        if not sess_id == msg.get('sessionId', None):
            return None
        
        t["url"] = urlparse(url = t["url"])._asdict()
        well_msg = {
            "targetId": t.get('targetId'),
            "targetInfo": t
        }
        self.logEvent(
            msg = json.dumps(well_msg),
            origin = "[Target Update to]"
        )
        return None
    
    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        return None

class targetDestroyHandler(Handler, interested_event = "Target.targetDestroyed"):
    _INSTANCE = None

    def __init__(self) -> None:
        self.called = 0
        pass

    async def handle(self, msg: Events.Target.targetDestroyed) -> None:
        tid = msg.get('params').get('targetId')
        async with self.trgt_session_lock:
            sessid = self._target_session.pop(tid, None)
        if not sessid:
            pass
        else:
            well_msg = {
                "targetId": tid,
                "sessionId": sessid
            }
            self.logEvent(
                msg = json.dumps(well_msg),
                origin = "[Target Destroyed]"
            )
        return None

    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        return None