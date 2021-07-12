from asyncio import windows_events
from itertools import tee
from typing import Callable, Dict, Literal, Optional, Tuple, TypedDict, Union, List
import asyncio
import hashlib
import copy
from urllib.parse import urlparse
import uuid
from copy import deepcopy
from inspect import currentframe, getframeinfo
import time

from core import ChromeBridge, Logger, create_window
from core import JSON as json
import chromeevents as Events
import chrometypes as Types
from chromods import FrameStatus, FrameStatusPool, NetworkSession, ScheduledNavigationPool, ScriptInfo, FrameScheduleInfo, NetworkInfo, StructuredUrl

MAX_LIVE_TIME = 5 #Second

class Handler(object):
    """
    Metaclass of all handlers. Each handler should only handle 'one' type of event. For example: Target.targetCreated
    The metaclss will assign event to proper sub-class handler.
    """

    cmd_lock = asyncio.Lock()
    trgt_session_lock = asyncio.Lock()
    frame_status_lock = asyncio.Lock()
    scheduled_navigation_lock = asyncio.Lock()

    _subhandlers: Dict[str, type] = {}
    _activedevent: Dict[str, int] = {}
    _pending_command: Dict[int, Types.Generic.DebugReply] = {}
    _target_session: Dict[Types.Target.TargetID, Union[Types.Target.SessionID, Literal["Pending"]]] = {}
    frameStatusPool: FrameStatusPool = {}
    scheduledNavigations: ScheduledNavigationPool = {}

    interface: ChromeBridge
    logger: Logger

    def __init_subclass__(cls, interested_event: Union[str, List[str]], output_events: List[str]) -> None:
        cls.interested_event = interested_event
        if cls._INSTANCE:
            return super().__init_subclass__()
        cls._INSTANCE = cls()
        if isinstance(interested_event, str):
            if _handler := (Handler._subhandlers.get(interested_event)):
                raise AttributeError(f"Attempting to register multiple handler on single type of event. Current Exsit Handler: {_handler.__class__}. Attempted adding Handler: {cls.__class__}")
            Handler._subhandlers[interested_event] = cls._INSTANCE
        elif isinstance(interested_event, list):
            for event_ in interested_event:
                if _handler := (Handler._subhandlers.get(event_)):
                    raise AttributeError(f"Attempting to register multiple handler on single type of event. Current Exsit Handler: {_handler.__class__}. Attempted adding Handler: {cls.__class__}")
                Handler._subhandlers[event_] = cls._INSTANCE
        
        for chromoEvent in output_events:
            if chromoEvent not in Handler._activedevent.keys():
                Handler._activedevent[chromoEvent] = max(Handler._activedevent.values(), default = 0) + 1
            else:
                # The output event can be emit by multiple handler.
                pass
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
                #print(f"[+ Dispatch Error] Handler for the event {event} are not implement yet with msg: {msg}")
                # raise NotImplementedError(f"[Dispatch Error] Handler for the event {event} are not implement yet")
                pass
            else:
                await cls._subhandlers.get(event).handle(msg)
            return None

        if mid := (msg.get('id')):
            async with cls.cmd_lock:
                cls._pending_command[mid] = msg
            return None
        
        print(f"[+ Dispatch Error] Handler does not recognize the message {msg}")
        return None
        #raise TypeError(f"[Dispatch Error] Handler does not recognize the message {msg}")

    async def sendCommand(
        self, 
        command: Types.Generic.DebugCommand,
    ) -> Types.Generic.DebugReply:
        """This method is an command interface for subhander to send command to debugee browser.
        This method are suggested to use `asyncio.create_task` for invoking based on performance
        
        Args:
            command (Types.Generic.DebugCommand): The command object to sending to
            callback (Callable[[Union[object, type], Types.Generic.DebugReply], asyncio.coroutines.types.CoroutineType])
        Return:
            message_id (int): The unique identifier of the command channel
        """
        async with self.cmd_lock:
            message_id = max(self._pending_command.keys(), default = 0) + 1
            self._pending_command[message_id] = None

        command['id'] = message_id
        self.interface.sendObj(command)

        while True:
            await asyncio.sleep(0)
            async with self.cmd_lock:
                msg = self._pending_command.get(message_id, None)
                if msg:
                    self._pending_command.pop(message_id)
            if msg:
                return msg
    
    def logEvent(
        self, 
        msg:str, 
        origin: Optional[str] = None, 
        debug: bool = False
    ) -> None:
        event_id = Handler._activedevent.get(origin, None)
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
            event = msg,
            debug = debug
        )
        return None
    
    @classmethod
    def disableEvent(cls, eventid: Union[str, int]) -> int:
        """Disable the event by the event id

        Args:
            eventid (int): The event id that tend to be diabled

        Returns:
            int: 0 if success else -1
        """
        if isinstance(eventid, int):
            if eventid < 0:
                print(f"[+ Event has been disabled]")
                return -1
            event_name = next(
                filter(
                    lambda x: x[1] == eventid, cls._activedevent.items()
                ),
                (None, None)
            )[0]
            if event_name:
                cls._activedevent[event_name] = -cls._activedevent[event_name]
            else:
                print(f"[+ Event not exist]")
                pass
            return 0
        elif isinstance(eventid, str):
            if eventid.isdigit():
                return cls.disableEvent(int(eventid))
            
            event_name = eventid
            eventid = cls._activedevent.get(event_name)

            if eventid is None:
                print(f"[+ Event not existed] {event_name}")
                return -1
            else:
                if cls._activedevent.get(event_name) < 0:
                    print(f"[+ Event has been disabled]: {event_name}")
                else:
                    cls._activedevent[event_name] = -eventid
                return 0
        else:
            print(f"[+ Invalid Type of eventid]: {type(eventid)}")
            return -1
    @classmethod
    def enableEvent(cls, eventid: Union[int,str]) -> int:
        if isinstance(eventid, int):
            if eventid < 0:
                print(f"[+ Invalid eventId] Event id {eventid} is negative.")
                return -1

            eventname = next(
                filter(
                    lambda x: -x[1] == eventid, cls._activedevent.items()
                ),
                (None, None)
            )[0]
            if not eventname:
                print(f"[+ Invalid eventId] No such event")
                return -1
            
            if cls._activedevent[eventname] < 0:
                cls._activedevent[eventname] = -cls._activedevent[eventname]
            else:
                return 0
            return 0
        if isinstance(eventid, str):
            if eventid.isdigit():
                return cls.enableEvent(int(eventid))
            
            event_name = eventid
            eventid = cls._activedevent.get(event_name)

            if not eventid:
                print(f"[+ Invalid eventName] No such event name: {event_name}")
                return -1
            if eventid < 0:
                cls._activedevent[event_name] = -eventid
                return 0
            else:
                return 0
        print(f"[+ Invalid eventId] The type of eventId should be int or str")
        return -1

    async def handle(self):
        """Event handle function. Due to it method may access parent class resource with synchronization issue.
        It should be designed as an `async` function. Once the meta class <Handler> resource are not as expected, it will
        return the control flow back to event loop
        """
        raise NotImplementedError("Metaclass not implement handle yet")
    
    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        """This is command handling function if the handler issue some command to debugee.
        Due to it may also access meta class <Handler> resource, it also designed as an a-
        synchronous method.
        """
        raise NotImplementedError("Metaclass not implement catchReply yet")

# Seal Done First, Secondly.
class TargetAttachedHandler(
    Handler, 
    interested_event = "Target.attachedToTarget", 
    output_events = [
        "[Main Frame Created]", 
        "[Sub-Frame Created]", 
        "[Frame Info Update to]", # For those urgent created
    ]
):
    _INSTANCE = None
    def __init__(self) -> None:
        pass
    
    async def handle(self, msg: Events.Target.attachedToTarget) -> None:
        """
        1. Examine if the attached target are frame, page.
            1-1 If it is not frame or page, memorize it as non-frame resource
        2. If attached target if frame or page, examine if the frame urgent created.
            2-1 If urgently created, emit [Frame Info Update to] and remove urgent tag.
                (scriptStatus, contacntedDomains remain)
            2-2 If not urgently created, still emit [Frame Info Update to]
        3. If attached target is not in frameStatusPool, add it.
            Emit [Main Frame Created or Sub-Frame Created]
        """
        t: Types.Target.TargetInfo = msg.get('params').get('targetInfo')
        t['url'] = urlparse(url = t.get('url'))._asdict()
        t['targetSessionId'] = msg.get('params').get('sessionId')

        session_id = msg.get('params').get('sessionId')
        target_id = t.get('targetId')
        target_type = t.get('type')
        #print(f"[+ Debugging] Target Attached to id {target_id}")
        async with super().trgt_session_lock:
            super()._target_session[target_id] = session_id

        if not t.get('type') in ['page', 'iframe']:
            # No Need to memorize it.
            await self.initTarget(targetId = target_id, targetType = target_type)
            return None
        
        # Processing frameStatusPool
        fid = t.get('targetId')
        if (frameStatus := self.frameStatusPool.get(fid)):
            #Frame Info Update Event and maybe frame create event
            if frameStatus.pop("urgent", False):
                # Frame has attached first.
                pass
            _msg = {
                "frameOriginUID": frameStatus.get('UID'),
                "frameId": fid,
            }
            self.frameStatusPool[fid]['title'] = t.get('title')
            self.frameStatusPool[fid]['url'] = t.get('url')
            self.frameStatusPool[fid]['mainFrame'] = True if t.get('type') == 'page' else False
            self.frameStatusPool[fid]['UID'] = uuid.uuid4().__str__()

            _msg['frameNewUID'] = self.frameStatusPool[fid]['UID']
            _msg['frameInfo'] = deepcopy(self.frameStatusPool[fid])
            _msg['frameInfo'].pop('contactedDomains', set())
            _msg['frameInfo'].pop('scriptStatus', {})
            _msg['frameInfo'].pop('networkSessions')
            _msg['frameInfo'].pop('navigationStatus')

            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Frame Info Update to]"
            )
            if (_openerFrameId := (t.get('openerFrameId'))):
                self.frameStatusPool[fid]['openerFrameUID'] =\
                    uid if (uid := (self.frameStatusPool.get(_openerFrameId).get('UID'))) else _openerFrameId
                _msg = {
                    "parentFrameUID": self.frameStatusPool[fid]['openerFrameUID'],
                    "frameUID": self.frameStatusPool[fid]['UID'],
                    "frameId": fid,
                    "frameInfo": deepcopy(self.frameStatusPool[fid])
                }

                _msg['frameInfo'].pop('contactedDomains', set())
                _msg['frameInfo'].pop('scriptStatus', {})

                self.logEvent(
                    msg = json.dumps(_msg),
                    origin = "[Main Frame Created]" if self.frameStatusPool[fid]['mainFrame'] else "[Sub-Frame Created]"
                )
            else:
                # No creation event has to handle
                pass
            await self.initTarget(targetId = target_id, targetType = target_type)
            return None
        
        # Frame Creation Only
        frameStatus = {
            "loaderId": None,
            "title": t.get('title'),
            "url": t.get('url'),
            "mainFrame": True if t.get('type') == 'page' else False,
            "UID": uuid.uuid4().__str__(),
            "contactedDomains": set(),
            "scriptStatus": dict(),
            "networkSessions": dict(),
            "navigationStatus": {
                "onScheduling": False,
                "reason": None,
                "destinationUrl": None,
                "script": None
            }
        }
        async with self.frame_status_lock:
            self.frameStatusPool[t.get('targetId')] = frameStatus
        _msg = {
            "parentFrameUID": self.frameStatusPool.get(t.get('openerFrameId'), {}).get("UID"),
            "frameUID": frameStatus.get('UID'),
            "frameId": t.get('targetId'),
            "frameInfo": deepcopy(frameStatus)
        }

        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')

        try:
            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Main Frame Created]" if frameStatus.get('mainFrame') else "[Sub-Frame Created]"
            )
        except:
            print(f"[+ Debugging] In {self.__class__.__name__}: {_msg}")
        await self.initTarget(targetId = target_id, targetType = target_type)
        return None
    
    async def catchReply(self, msg: Types.Generic.DebugReply) -> None:
        return None

    async def initTarget(self, targetId: Types.Target.TargetID, targetType: str):
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
        await self._enablePage(
            sessionId = sessionid
        )
        await self._enableNetwork(
            sessionId = sessionid
        )
        await self._enableDebugger(
            sessionId = sessionid
        )
        await self._enableFileChooserEvent(
            sessionId = sessionid,
            enable = True
        )
        await self._enableDOM(
            sessionId = sessionid
        )
        if targetType == "browser":
            await self._enableDownloadEvents(
                sessionId = sessionid,
                enable = True
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
        msg = await self.sendCommand(command = _cmd)
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
        msg = await self.sendCommand(command = _cmd)
        return None
    
    async def _enablePage(self, sessionId: Types.Target.SessionID) -> None:
        _cmd: Types.Generic.DebugCommand = {
            "method": "Page.enable",
            "sessionId": sessionId
        }
        msg = await self.sendCommand(command = _cmd)
        return None
    
    async def _enableNetwork(self, sessionId: Types.Target.SessionID) -> None:
        _cmd: Types.Generic.DebugCommand = {
            "method": "Network.enable",
            "sessionId": sessionId
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "Network.setAttachDebugStack",
            "sessionId": sessionId,
            "params": {
                "enabled": True
            }
        }
        msg = await self.sendCommand(command = _cmd)
        return None
    
    async def _enableDebugger(self, sessionId: Types.Target.SessionID) -> None:
        """Enable Debugger on attached target to recieve javascript parsed event.
        For more information, please refer to the following urls:
        - (script parsed event) https://chromedevtools.github.io/devtools-protocol/tot/Debugger/#event-scriptParsed (2021/04/12)
        - (enabled debugger) https://chromedevtools.github.io/devtools-protocol/tot/Debugger/#method-enable (2021/04/12)

        Args:
            sessionId (Types.Target.SessionID): The session id for the target

        Returns:
            None: This method return sentinal object
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Debugger.enable",
            "sessionId": sessionId
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "Debugger.setAsyncCallStackDepth",
            "sessionId": sessionId,
            "params": {
                "maxDepth": 20
            }
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "Runtime.enable",
            "sessionId": sessionId
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "Runtime.setAsyncCallStackDepth",
            "sessionId": sessionId,
            "params": {
                "maxDepth": 20
            }
        }
        msg = await self.sendCommand(command = _cmd)
        return None

    async def _enableLifecycleEvents(self, sessionId: Types.Target.SessionID, enable: bool = True) -> None:
        """Enable life cycle event of attached target(page) such as navigation, load, paint, etc
        For more information, please refer to the following link:
        - https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-setLifecycleEventsEnabled (2021/04/12)

        Args:
            sessionId (Types.Target.SessionID): [description]
            enable (bool, optional): [description]. Defaults to True.

        Returns:
            None: This function return sentinal object.
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Page.setLifecycleEventsEnabled",
            "sessionId": sessionId,
            "params": {
                "enabled": enable
            }
        }
        msg = await self.sendCommand(command = _cmd)
        return None
    
    async def _enableDownloadEvents(self, sessionId: Types.Target.SessionID, enable: bool = True) -> None:
        """Enable download event triggered by browser and give us which frame initiate the download.
        For more information, redirect yourself to the document:
        - https://chromedevtools.github.io/devtools-protocol/tot/Browser/#event-downloadWillBegin (2021/04/12)

        Args:
            sessionId (Types.Target.SessionID): The session id of the attached browser target
            enable (bool, optional): Enable or not. Defaults to True.
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Browser.setDownloadBehavior",
            "sessionId": sessionId,
            "params": {
                "behavior": "allow", # Allowed value: "deny", "allow", "allowAndName", "default"
                "eventsEnabled": enable
            }
        }
        msg = await self.sendCommand(command = _cmd)
        return None
    
    async def _enableFileChooserEvent(self, sessionId: Types.Target.SessionID, enable: bool = True) -> None:
        """Enable the `page` target for issuing file choosing dialog when upload or doanload file.
        For more information, please refering to the following url:
        - https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-setInterceptFileChooserDialog (2021/04/12)

        Args:
            sessionId (Types.Target.SessionID): The session id for the target page
            enable (bool, optional): Enable the page to emit the event or not. Defaults to True.

        Returns:
            None: This method return a sentinal object.

        Note:
            [EXPERIMENTAL] - 2021/04/12
        """
        _cmd: Types.Generic.DebugCommand = {
            "method": "Page.setInterceptFileChooserDialog",
            "sessionId": sessionId,
            "params":{
                "enabled": enable
            }
        }
        msg = await self.sendCommand(command = _cmd)
        return None

    async def _enableDOM(self, sessionId: Types.Target.SessionID):
        _cmd: Types.Generic.DebugCommand = {
            "method": "DOM.enable",
            "sessionId": sessionId,
            "params": {}
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "DOM.setNodeStackTracesEnabled",
            "sessionId": sessionId,
            "params":{
                "enable": True
            }
        }
        msg = await self.sendCommand(command = _cmd)
        _cmd: Types.Generic.DebugCommand = {
            "method": "DOM.focus",
            "sessionId": sessionId,
            "params":{}
        }
        msg = await self.sendCommand(command = _cmd)

class TargetCreatedHandler(
    Handler, 
    interested_event = "Target.targetCreated",
    output_events = []
):
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
                        self._target_session[t.get("targetId")] = "Pending"
                if not _pending:
                    await self._attachToTarget(t)
                else:
                    # There are same Target Creation in previous
                    pass
        return None

    async def catchReply(self, msg: Types.Generic.DebugReply) -> None:
        """It may not be called directly from human. It will be call by metaclass `Handler`
        Args:
            command (Types.Generic.DebugCommand): The command sent by the handler
            msg (Type.Generic.DebugReply): The reply for the `command`
        """

        # Register targetId for relative sessionId
        
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
        msg = await self.sendCommand(command = _cmd)
        return None

class targetInfoChangeHandler(
    Handler, 
    interested_event = "Target.targetInfoChanged",
    output_events = ["[Frame Info Update to]"]
):
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
        if not t.get("type") in ['page', 'iframe']:
            return None
        
        frameStatus: FrameStatus = self.frameStatusPool.get(t.get("targetId"))
        if not frameStatus:
            # Maybe urgent?
            return None
        
        if (not frameStatus.get('title')) and frameStatus.get('url') == t.get('url'):
            if t.get('title'):
                self.frameStatusPool[t.get("targetId")]['title'] = t.get('title')
            msg = {
                "frameOriginUID": self.frameStatusPool[t.get("targetId")].pop("UID"),
                "frameId": t.get("targetId")
            }
            self.frameStatusPool[t.get("targetId")]['UID'] = uuid.uuid4().__str__()
            msg['frameNewUID'] = self.frameStatusPool[t.get("targetId")]['UID']
            msg['frameInfo'] = deepcopy(self.frameStatusPool[t.get("targetId")])
            msg['frameInfo'].pop('scriptStatus')
            msg['frameInfo'].pop('contactedDomains')
            msg['frameInfo'].pop('networkSessions')
            msg['frameInfo'].pop('navigationStatus')

            self.logEvent(
                msg = json.dumps(msg),
                origin = "[Frame Info Update to]"
            )

        well_msg = {
            "targetId": t.get('targetId'),
            "targetInfo": t
        }
        """
        self.logEvent(
            msg = json.dumps(well_msg),
            origin = "[Target Update to]"
        )
        """
        return None
    
    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        return None

class targetDestroyHandler(
    Handler, 
    interested_event = "Target.targetDestroyed",
    output_events = ["[Target Destroyed]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        self.called = 0
        pass

    async def handle(self, msg: Events.Target.targetDestroyed) -> None:
        assert msg.get('method') == "Target.targetDestroyed"
        destroyedTargetId = msg.get('params').get('targetId')
        
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
        frameStatus = self.frameStatusPool.pop(destroyedTargetId, {})
        if frameStatus:
            self.scheduledNavigations.pop(frameStatus.get('UID'), None)
        return None

    async def catchReply(self, command: Types.Generic.DebugCommand, msg: Types.Generic.DebugReply):
        return None

# Seal Done First, Secondly.
class frameAttachedHandler(
    Handler, 
    interested_event = "Page.frameAttached",
    output_events = [
        "[Frame Attach to Frame]", # Urgent Created if attached parent not exist
        "[Script Create Sub-Frame]",
        "[Sub-Frame Created]" # Urgent Creation
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Page.frameAttached) -> None:
        """
        1. Examine if child frame existed in frameStatusPool
            1-1 If child Existed in frameStatusPool, examine if urgent.
                If it is urgent created, only add attaching event, do not update
                frameUID. And remove urgent tag.
            1-2 If child not existed in frameStatusPool, add it.
        2. Examine if parent frame existed in frameStatusPool.
            2-1 If parent not existed in frameStatusPool, urgent create it.
            2-2 If parent existed, it is normal.
        Emit [Frame Attach to Frame]
        TODO
        3. Looking for Script <domain>/<hash> for any possible frame/target
            3-1 Find script in parent frame if parent frame not urgent created
            3-1 If not found any script, emit other type of [Script Create Sub-Frame]
            Emit [Script Create Sub-Frame]
        """
        event_ = msg.get('params')
        childFrameId = event_.get('frameId')
        targetId = event_.get('parentFrameId')
        backendTargetId: Types.Target.TargetID = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'),
                super()._target_session.items()
            )
        )[0]

        # Process Child Frame First.
        childFrameStatus: Optional[FrameStatus] = deepcopy(self.frameStatusPool.get(childFrameId))
        if childFrameStatus:
            # Urgent Created Before?
            _urgency = childFrameStatus.pop("urgent", False)
            if not _urgency:
                pass
            pass
        else:
            childFrameStatus: FrameStatus = {
                "loaderId": None,
                "openerFrameUID": None,
                "title": None,
                "url": None,
                "mainFrame": False,
                "UID": uuid.uuid4().__str__(),
                "contactedDomains": set(),
                "scriptStatus": dict(),
                "networkSessions": dict(),
                "navigationStatus": {
                    "onScheduling": False,
                    "reason": None,
                    "destinationUrl": None,
                    "script": None
                }
            }
            self.frameStatusPool[event_.get('frameId')] = childFrameStatus
            pass

        # Process Parent(target) Frame Secondly.
        targetFrameStatus = deepcopy(self.frameStatusPool.get(targetId))
        if not targetFrameStatus:
            #print(f"[+ Debugging] In {self.__class__.__name__} event, target frame not found in the frameId: {targetId}")
            # Urget Creation of Parent
            parentFrameStatus: FrameStatus = {
                "loaderId": None,
                "openerFrameUID": None,
                "title": None,
                "url": None,
                "mainFrame": None,
                "UID": uuid.uuid4().__str__(),
                "contactedDomains": set(),
                "scriptStatus": dict(),
                "urgent": True,
                "networkSessions": dict(),
                "navigationStatus": {
                    "onScheduling": False,
                    "reason": None,
                    "destinationUrl": None,
                    "script": None
                }
            }
            self.frameStatusPool[targetId] = parentFrameStatus
            targetFrameStatus = parentFrameStatus
        
        # Emitting Frame Attach to Frame
        _msg = {
            "parentFrameUID": targetFrameStatus.get('UID'),
            "parentFrameId": targetId,
            "frameUID": childFrameStatus.get('UID'),
            "frameId": event_.get('frameId'),
            "frameInfo": deepcopy(childFrameStatus)
        }
        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')
        _msg['frameInfo'].pop('networkSessions')
        _msg['frameInfo'].pop('navigationStatus')
        self.logEvent(
            msg = json.dumps(_msg),
            origin = "[Frame Attach to Frame]"
        )
        

        stack_: Types.Runtime.StackTrace = event_.get('stack')

        if stack_:
            # Emit Script create subframe
            backendTargetStatus = targetFrameStatus
            for callframe_ in stack_.get('callFrames'):
                scriptInfo: ScriptInfo = backendTargetStatus.get('scriptStatus').get(callframe_.get('scriptId'))
                if scriptInfo: break
            
            if not scriptInfo:
                backendTargetStatus = self.frameStatusPool.get(backendTargetId)
            
            for callframe_ in stack_.get('callFrames'):
                if scriptInfo: break
                scriptInfo: ScriptInfo = backendTargetStatus.get('scriptStatus').get(callframe_.get('scriptId'))
            
            stack_bottom = stack_.get('callFrames')[0]
            _msg = {
                "Script": deepcopy(scriptInfo) if scriptInfo else stack_bottom,
                "frameUID": childFrameStatus.get('UID'),
                "frameId": event_.get('frameId')
            }
            _msg['Script'].pop('contactedDomains', None)
            _msg['Script'].pop('httpGetUrls', None)

            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Script Create Sub-Frame]"
            )
        else:
            pass
        return None

class downloadWillBeginHandler(
    Handler, 
    interested_event = ["Page.downloadWillBegin", "Browser.downloadWillBegin"],
    output_events = ["[File Download Start]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Browser.downloadWillBegin) -> None:
        print("[+ Debugging] File download starging...")
        event_ = msg.get('params')
        event_["url"] = urlparse(event_["url"])._asdict()
        _msg = {
            "frameUID": self.frameStatusPool[event_.get('frameId')].get('UID'),
            "frameId": event_.get('frameId'),
            "downloadUID": event_.get('guid'),
            "fileName": event_.get('suggestedFilename'),
            "downloadInfo": event_
        }
        self.logEvent(
            msg = json.dumps(_msg),
            origin = "[File Download Start]"
        )
        return None

class fileChooserOpenedHandler(
    Handler, 
    interested_event = "Page.fileChooserOpened",
    output_events = ["[File Chooser Opened]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Page.fileChooserOpened) -> None:
        event_ = msg.get('params')
        self.logEvent(
            msg = json.dumps(event_),
            origin = "[File Chooser Opened]",
            debug = True
        )
        return None

# Seal Done First , Secondly
class scriptParsedHandler(
    Handler, 
    interested_event = "Debugger.scriptParsed",
    output_events = [
        "[Frame Execute Script]", 
        "[Script Initiate Remote Script]",
        "[Script Spawn Script]",
        "[Script Call Script]"
    ]
):
    """In this handler, we will be able to see the event of remote javascript loaded
    by local v8. In face, the script parsed is not so important. If we have network
    visibility, we can directly see which script will be requested. (Hope so)
    """
    _INSTANCE = None

    def __init__(self) -> None:
        self.m = hashlib.md5()
        return None
    
    async def handle(self, msg: Events.Debugger.scriptParsed) -> None:
        """
        1. If only url exist: 
            i.    [Frame Execute Script] will be triggered.
            ii.   statusFramePool will add a script
        2. If only stack exist:
            i.    [Frame Execute Script] will be triggered.
            ii.   [Script Spawn Script] will be triggered.
            iii.  statusFramePool updated a script
        3. If both exist:
            i.   [Frame Execute Script] will be triggered.
            ii.  statusFramePool will update a script 
        """

        evt_ = msg.get('params')
        event_ = {
            "scriptId": evt_.get("scriptId"),
            "url": urlparse(url = evt_.get('url'))._asdict() if evt_.get('url') else {},
            "contentHash": evt_.get("hash", ""),
            "sourceMapURL": urlparse(url = evt_.get("sourceMapURL", ""))._asdict(),
            "hasSourceURL": evt_.get("hasSourceURL", ""),
            "stack": evt_.get("stackTrace", {}),
            "scriptLanguage": evt_.get("scriptLanguage"),
            "debugSymbols": evt_.get("debugSymbols"),
            "embedderName": evt_.get("embedderName")
        }
        if evt_.get("stackTrace"):
            pass
            #print(json.dumps(evt_, indent = 4))
        _scheme = event_.get("url").get("scheme", "")
        event_['targetId'] = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'), 
                self._target_session.items()
            ), 
            ("unknown", "")
        )[0]
        tid = event_['targetId']
        sid = event_.get('scriptId')
        fid = evt_.get('executionContextAuxData', {}).get('frameId')
        if not fid:
            print(f"[+ Debugging] In {self.__class__.__name__}: {evt_}")
            exit(0)

        frameStatus = self.frameStatusPool.get(fid)
        if not frameStatus:
            rsp = await self.sendCommand(
                command = {
                    "method": "Target.setDiscoverTargets",
                    "sessionId": sid,
                }
            )
            trgts: List[Types.Target.TargetInfo] = rsp.get('result').get('targetInfos')
            for target in trgts:
                if target.get('targetId') == fid:
                    print("[+ debugging] Frame is target but not attached yet")
            print("[+ debugging] Error get frame status")
            exit(0)
        
        # Constructing ScriptStatus and update it to frameStatus
        url_: Union[StructuredUrl, dict] = urlparse(evt_.get('url'))._asdict() if evt_.get('url') else {}
        scriptInfo: ScriptInfo = {
            "url": url_,
            "domain": url_.get('netloc') if url_ else "",
            "contentHash": evt_.get('hash'),
            "contactedDomains": set(),
            "httpGetUrls": set(),
            "callScriptHistory": set(),
            "spawnScriptHistory": set()
        }
        frameStatus["scriptStatus"][sid] = scriptInfo

        parentScriptId, parentScriptInfo = None, None

        if (stack_ := (evt_.get('stackTrace'))):
            callframes = stack_.get("callFrames")
            s = stack_
            while (s := s.get('parent')):
                callframes.extend(s.get("callFrames"))
            stack_["callFrames"] = callframes
            for callFrame in stack_.get("callFrames"):
                if not isinstance(callFrame, dict):
                    print(f"[+ Debugging] CallFrame is {callFrame}")
                    break
                
                parentScriptId = callFrame.get('scriptId')
                parentScriptInfo = frameStatus.get("scriptStatus").get(parentScriptId)
                if parentScriptInfo:
                    break
            if not parentScriptInfo:
                """
                TODO: Considering to maintain timeline of frame.
                """
                #print(f"[+ Debugging]: No parent script found: {event_}")
                #print(f"[+ debugging] tid: {tid}")
                #print(f"[+ debugging] psid: {parentScriptId}")
                pass
                return None

            if not 'spawnScriptHistory' in parentScriptInfo:
                print(parentScriptInfo)

            if scriptInfo.get('contentHash') in parentScriptInfo.get('spawnScriptHistory', set()):
                return None
            parentScriptInfo["spawnScriptHistory"].add(scriptInfo.get('contentHash'))

            script_initiate_info = {
                "frameUID": uid if (uid := (frameStatus.get('UID'))) else tid,
                "parentScriptInfo": deepcopy(parentScriptInfo),
                "Script": deepcopy(scriptInfo)
            }
            self.logEvent(
                msg = json.dumps(script_initiate_info),
                origin = "[Script Spawn Script]"
            )
            self.handleStackTrace(strace = stack_, frameStatus = frameStatus)
        # Emit [Frame Execute Script]
        exe_msg = {
            "frameUID": uid if (uid := (frameStatus.get('UID'))) else tid,
            "Script": deepcopy(scriptInfo),
            "ScriptId": sid
        }
        if not _scheme.endswith("-extension"):
            self.logEvent(
                msg = json.dumps(exe_msg),
                origin = "[Frame Execute Script]"
            )
        return None

    def handleStackTrace(self, strace: Types.Runtime.StackTrace, frameStatus: FrameStatus):
        #print(f"[+ Debugging] handleStackTrace called")
        #print(f"StackTrace: {strace}")
        #print("=======================")
        slide_window = create_window(i = strace.get("callFrames"), window_size = 2)
        cross_call_scripts = [
            (callee, caller) 
            for callee, caller in slide_window if not (callee.get('scriptId') == caller.get('scriptId'))
        ]
        #print("=======================")
        #print(f"Cross Script Calls: {cross_call_scripts}")
        scriptInfo_pair = [
                (
                    frameStatus.get('scriptStatus').get(callee.get('scriptId'), callee),
                    frameStatus.get('scriptStatus').get(caller.get('scriptId'), caller)
                ) for callee, caller in cross_call_scripts
        ]
        if not scriptInfo_pair:
            return None
        try:
            output_context = [
                {
                    "frameUID": frameStatus.get('UID'),
                    "callerScript": caller_info,
                    "calleeScirpt": callee_info
                } for callee_info, caller_info in scriptInfo_pair if callee_info.get('contentHash', "") not in caller_info.get('callScriptHistory', set())
            ]
        except:
            print(scriptInfo_pair)
        [self.logEvent(msg = json.dumps(x), origin = "[Script Call Script]") for x in output_context]
        [caller["callScriptHistory"].add(callee.get('contentHash')) for callee, caller in scriptInfo_pair if isinstance(callee, dict) and isinstance(caller, dict) and isinstance(caller.get('callScriptHistory'), set)]
        pass

# Seal Done First, Secondly.
class frameNavigatedHandler(
    Handler,
    interested_event = "Page.frameNavigated",
    output_events = [
        "[Frame Navigate by Script]", 
        "[Frame Navigate by HTTP]", 
        "[Frame Navigate by HTML]", 
        "[Frame Navigate by User]",
        "[Frame Navigate by Other]",
        "[Sub-Frame Created]"
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        self.initiator_map = {
            "user": "User",
            "http": "HTTP",
            "html": "HTML",
            "script": "Script",
            "other": "Other"
        }
        return None
    
    async def handle(self, msg: Events.Page.frameNavigated) -> None:
        """
        1. Get navigation information from scheduledNavigations
        2. Delete item in scheduledNavigations
        2. Update frameStatusPool, ie. UID, contactedDomains, scriptStatus
            2-1. If Urgent Creation Needed, Urgent Creation.
        3. Emit [Frame Navigate by User/HTTP/HTML/Other]
        """
        targetId: Types.Target.TargetID = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'),
                super()._target_session.items()
            )
        )[0]

        event_: Types.Page.Frame = msg.get('params').get('frame')
        frameId = event_.get('id')

        # Basic sanitizing check
        if not targetId == frameId:
            #print(f"[+ Debugging] targetId: {targetId} is not consistent ot frameId: {frameId}")
            # This might happen in when frame just navigated, but still not attachable.
            # If frame become attachable, we may attach to debugger asap.
            # So, `frameId` still dominent.
            pass

        originFrameStatus = deepcopy(self.frameStatusPool.get(frameId))
        if not originFrameStatus:
            #print(f"[+ Debugging] In {self.__class__.__name__}, no original navigated frame found in frameId: {frameId}. Urgent Creating...")
            
            frameStatus: FrameStatus = {
                "loaderId": event_.get('loaderId'),
                "openerFrameUID": None,
                "title": None,
                "url": urlparse(event_.get('url'))._asdict(),
                "mainFrame": False,
                "UID": uuid.uuid4().__str__()
            }
            _msg = {
                "frameId": frameId,
                "frameUID": frameStatus.get("UID"),
                "frameInfo": deepcopy(frameStatus)
            }

            frameStatus["urgent"] = True
            frameStatus["scriptStatus"] = dict()
            frameStatus["contactedDomains"] = set()
            frameStatus["networkSessions"] = dict()
            frameStatus["navigationStatus"] = {
                "onScheduling": False,
                "reason": None,
                "destinationUrl": None,
                "script": None
            }

            originFrameStatus = frameStatus
            self.frameStatusPool[frameId] = frameStatus

            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Frame Navigate by Other]"
            )
            return None

        async with self.scheduled_navigation_lock:
            reasons = self.scheduledNavigations.pop(originFrameStatus.get('UID'), {"reason": "user"})
            if not reasons:
                print(f"[+ debugging] No navigation request for frame navigation: {originFrameStatus.get('UID')}")
                reasons = {
                    "reason": "other"
                }
        async with self.frame_status_lock:
            if not originFrameStatus:
                print(f"[+ Debugging] No origin frame found with frameId: {frameId}")
                return None
        
        schedule_ticket: FrameScheduleInfo  = originFrameStatus.get('navigationStatus')

        self.frameStatusPool[frameId]['UID'] = uuid.uuid4().__str__()
        self.frameStatusPool[frameId]['contactedDomains'] = set()
        self.frameStatusPool[frameId]['scriptStatus'] = dict()
        self.frameStatusPool[frameId]['url'] = urlparse(url = event_.get('url'))._asdict()
        self.frameStatusPool[frameId]['loaderId'] = event_.get('loaderId')
        self.frameStatusPool[frameId]["networkSessions"] = {}
        self.frameStatusPool[frameId]['navigationStatus'] = {
            "onScheduling": False,
            "reason": None,
            "destinationUrl": None,
            "script": None
        }

        _msg = {
            "frameUID": self.frameStatusPool[frameId]['UID'],
            "frameId": frameId,
            "originFrameUID": originFrameStatus.get('UID'),
            "originFrameId": frameId,
            "frameInfo": deepcopy(self.frameStatusPool[frameId]),
            "script": schedule_ticket.get('script') if (schedule_ticket.get('onScheduling') and schedule_ticket.get('reason') == "script") else None
        }
        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')
        _msg['frameInfo'].pop('networkSessions')
        _msg['frameInfo'].pop('navigationStatus')

        if _msg['script']:
            _msg['script'].pop('contactedDomains')
            _msg['script'].pop('httpGetUrls')

        self.logEvent(
            msg = json.dumps(_msg),
            origin = f"[Frame Navigate by {self.initiator_map.get(reasons.get('reason'))}]"
        )
        return None

# Seal Done First 
class frameRequestNavigationHandler(
    Handler,
    interested_event = "Page.frameRequestNavigation",
    output_events = []
):
    _INSTANCE = None

    def __init__(self) -> None:
        self.reason_map = {
            "httpHeaderRefreash": "http",
            "scriptInitiated": "script",
            "metaTagRefresh": "html"
        }
        return None
    
    async def handle(self, msg: Events.Page.frameRequestNavigation) -> None:
        """
        1. Add event to scheduledNavigations
        """
        event_ = msg.get('params')
        async with self.frame_status_lock:
            frameUID = self.frameStatusPool.get(event_.get('frameId')).get('UID')
            self.frameStatusPool[event_.get('frameId')]["navigationStatus"]["onScheduling"] = True
            self.frameStatusPool[event_.get('frameId')]["navigationStatus"]["reason"] = \
                reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "other"
            self.frameStatusPool[event_.get('frameId')]["navigationStatus"]["url"] = \
                event_.get('url')
        
        if not frameUID:
            frameUID = event_.get('frameId')
            pass
        async with self.scheduled_navigation_lock:
            if self.scheduledNavigations.get(frameUID):
                return None
            
            self.scheduledNavigations[frameUID] = {
                "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "other",
                "disposition": None
            }
        return None

# Seal Done First 
class frameSheduledNavigationHandler(
    Handler,
    interested_event = "Page.frameScheduledNavigation",
    output_events = [] # Possible Urgent Creation
):
    _INSTANCE = None

    def __init__(self):
        self.reason_map = {
            "httpHeaderRefreash": "http",
            "scriptInitiated": "script",
            "metaTagRefresh": "html",
            "anchorClick": "user"
        }
        return None
    
    async def handle(self, msg: Events.Page.frameScheduledNavigation):
        event_ = msg.get('params')
        async with self.frame_status_lock:
            frameStatus: Optional[FrameStatus] = self.frameStatusPool.get(event_.get('frameId'))
        
        if not frameStatus:
            # Need Urgent Creation of Scheduled Navigated Frame
            # Frame Schedule Navigation before it attach or create.
            frameStatus: FrameStatus = {
                "loaderId": None,
                "openerFrameUID": None,
                "title": None,
                "url": {},
                "mainFrame": False,
                "UID": uuid.uuid4().__str__(),
                "contactedDomains": set(),
                "scriptStatus": dict(),
                "urgent": True,
                "navigationStatus": {
                    "onScheduling": True,
                    "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "other",
                    "destinationUrl": event_.get('url'),
                    "script": None
                }
            }
            self.frameStatusPool[event_.get('frameId')] = frameStatus
        frameUID = frameStatus.get('UID')
        
        async with self.scheduled_navigation_lock:
            if self.scheduledNavigations.get(frameUID):
                return None
            
            self.scheduledNavigations[frameUID] = {
                "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "other",
                "disposition": None
            }
        frameStatus["navigationStatus"] = {
            "onScheduling": True,
            "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "other",
            "destinationUrl": event_.get('url'),
            "script": None
        }
        return None

# Todo
class requestWillBeSentHandler(
    Handler,
    interested_event = "Network.requestWillBeSent",
    output_events = [
        "[Host Redirect to Host]",
        "[Script Request to Host]",
        "[Frame Request to Host]",
        "[Script Call Script]"
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Network.requestWillBeSent) -> None:
        assert msg.get("method") == "Network.requestWillBeSent"
        event_ = msg.get("params")
        rid = event_.get('requestId')
        # Find reqeust sender FrameId
        frameStatus: FrameStatus = self.frameStatusPool.get(fid) if (fid := (event_.get("frameId"))) else None
        if not frameStatus:
            backendTargetId: Types.Target.TargetID = next(
                filter(
                    lambda x: x[1] == sessid,
                    super()._target_session.items()
                )
            )[0] if (sessid := (msg.get('sessionId'))) else None
            frameStatus = self.frameStatusPool.get(backendTargetId)
        
        if not frameStatus:
            print(f"[+ Debugging] In line number {getframeinfo(currentframe()).lineno}: frameStatus not exist")
            print(f"[+ Debugging] And it might need implement urgent creation... So bad~~~")
            exit()
        
        n_sessions = frameStatus.get('networkSessions')
        now = time.time()
        if n_sessions:
            frameStatus["networkSessions"] = {rid: n_sessions[rid] for rid in n_sessions if now - n_sessions[rid].get('bornTime') < MAX_LIVE_TIME}

        new_sesion: NetworkSession = {
            "request": event_.get('request'),
            "response": None
        }

        current_session: Union[NetworkInfo] = frameStatus.get("networkSessions").get(rid)
        if current_session:
            current_session["session"].append(new_sesion)
            return None

        n_sessions[rid] = {
            "bornTime": time.time(),
            "session": list()
        }
        n_sessions[rid]["request"] = event_.get('request')

        # Seem if script initiatd or frame initiated
        initiator = event_.get('initiator')
        if initiator.get('type') == 'script':
            # Try to emit [Script Initiate Contact to]
            stack_ = initiator.get("stack")
            s = stack_
            if not s:
                print(f"[+ Debugging] In {self.__class__.__name__}: initiator is script but no stack found. Event message is: {json.dumps(event_, indent = 4)}")
                pass
            callframes = s.get("callFrames")
            while (s := s.get('parent')):
                callframes.extend(s.get('callFrames'))
            scriptInfo = None

            stack_["callFrames"] = callframes
            for stackFrame in stack_.get("callFrames"):
                sid = stackFrame.get("scriptId")
                scriptInfo = frameStatus.get("scriptStatus").get(sid)
                if scriptInfo: break
            if not stack_.get("callFrames"):
                print(f"[+ Debugging] initiator is script but no stacktrace: {event_}")
                exit()
                pass
            if not scriptInfo:
                script_url = urlparse(stackFrame.get("url"))._asdict()
                scriptInfo: ScriptInfo = {
                    "domain": script_url.get("netloc"),
                    "url": script_url,
                    "contentHash": "unknown",
                    "contactedDomains": set(),
                    "spawnScriptHistory": set(),
                    "httpGetUrls": set()
                }
                frameStatus["scriptStatus"][sid] = scriptInfo
            scriptParsedHandler._INSTANCE.handleStackTrace(stack_, frameStatus)

            if not event_.get('request').get('method') == "GET":
                return None
            if not frameStatus.get('navigationStatus').get('onScheduling'):
                return None
            if not frameStatus.get('navigationStatus').get('reason') == "script":
                return None
            if frameStatus.get('navigationStatus').get('destinationUrl') == event_.get('request').get('url'):
                frameStatus["navigationStatus"]["script"] = scriptInfo
                frameStatus["navigationStatus"]["networkSession"] = frameStatus.get("networkSessions").get(rid)
            pass
        elif initiator.get("type") == 'other':
            # Try to emit [Frame Initiate Contact to]
            # Try to emit [Frame Receive Script Resource from]
            if not event_.get('request').get('method') == "GET":
                return None
            if not frameStatus.get('navigationStatus').get('onScheduling'):
                return None
            if not frameStatus.get('navigationStatus').get('reason') == "user":
                return None
            if frameStatus.get('navigationStatus').get('destinationUrl') == event_.get('request').get('url'):
                frameStatus["navigationStatus"]["networkSession"] = frameStatus.get("networkSessions").get(rid)
            pass
        pass
        
        # See if redirection happened? Emit [Host Redirect to Host]
        return None

class responseReceivedHandler(
    Handler,
    interested_event = "Network.responseReceive",
    output_events = []
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Network.responseReceived) -> None:
        event_ = msg.get('params')
        rid = event_.get('requestId')
        loaderId = event_.get('loaderId')
        frameId = event_.get('frameId')

        if not frameId:
            return None
        frameStatus = self.frameStatusPool.get(frameId)

        """
        if not frameStatus.get('loaderId') == loaderId:
            print(f"[+ Debugging] In {self.__class__.__name__}: frameId and LoaderId inconsistent, loaderId: {loaderId}, frameStatus: {json.dumps(frameStatus, default = lambda o: None)}")
            exit()
        """
        n_sessions = frameStatus.get('networkSessions')
        sess = n_sessions.get(rid)

        if not sess:
            return None
        
        head = sess["session"][-1]
        if not head:
            return None
        if head.get('response'):
            return None
        
        head["response"] = event_.get('response')
        pass