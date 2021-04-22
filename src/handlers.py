from typing import Callable, Dict, Literal, Optional, Tuple, Union, List
import chromeevents as Events
import chrometypes as Types
import json
import asyncio
import hashlib
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
    _pending_command: Dict[int, Types.Generic.DebugReply] = {}
    _target_session: Dict[Types.Target.TargetID, Union[Types.Target.SessionID, Literal["Pending"]]] = {}
    interface: ChromeBridge
    logger: Logger

    def __init_subclass__(cls, interested_event: str, output_events: List[str]) -> None:
        cls.interested_event = interested_event
        if cls._INSTANCE:
            return super().__init_subclass__()
        cls._INSTANCE = cls()
        if _handler := (Handler._subhandlers.get(interested_event)):
            raise AttributeError(f"Attempting to register multiple handler on single type of event. Current Exsit Handler: {_handler.__class__}. Attempted adding Handler: {cls.__class__}")
        Handler._subhandlers[interested_event] = cls._INSTANCE
        for chromoEvent in output_events:
            Handler._activedevent[chromoEvent] = max(Handler._activedevent.values(), default = 0) + 1
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
    
    def logEvent(self, msg:str, origin: Optional[str] = None, debug: bool = False) -> None:
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

class TargetAttachedHandler(
    Handler, 
    interested_event = "Target.attachedToTarget", 
    output_events = ["[Target Attached]"]
):
    _INSTANCE = None
    def __init__(self) -> None:
        pass
    
    async def handle(self, msg: Events.Target.attachedToTarget) -> None:
        t: Types.Target.TargetInfo = msg.get('params').get('targetInfo')
        t['url'] = urlparse(url = t.get('url'))._asdict()
        t['targetSessionId'] = msg.get('params').get('sessionId')

        session_id = msg.get('params').get('sessionId')
        target_id = msg.get('params').get('targetInfo').get('targetId')
        target_type = msg.get('params').get('targetInfo').get('type')

        async with super().trgt_session_lock:
            super()._target_session[target_id] = session_id

        self.logEvent(
            msg = json.dumps(t),
            origin = "[Target Attached]"
        )
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
    output_events = ["[New Target Created]"]
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
                    self.logEvent(
                        msg = json.dumps(t),
                        origin = "[New Target Created]"
                    )
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
    output_events = ["[Target Update to]"]
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
    
class frameAttachedHandler(
    Handler, 
    interested_event = "Page.frameAttached",
    output_events = ["[Frame Attach to Frame]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Page.frameAttached) -> None:
        event_ = msg.get('params')
        stack_ = event_.get('stack')
        if stack_:
            event_['stack']['callFrames'] = stack_.get('callFrames')[0]
            event_['stack']['callFrames']['url'] = urlparse(url = event_.get('stack').get('callFrames').get('url'))._asdict()
            event_['stack']['callFrames'].pop('lineNumber')
            event_['stack']['callFrames'].pop('columnNumber')
        else:
            pass
        self.logEvent(
            msg = json.dumps(event_),
            origin = "[Frame Attach to Frame]"
        )
        return None


class downloadWillBeginHandler(
    Handler, 
    interested_event = "Page.downloadWillBegin",
    output_events = ["[File Download Start]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Browser.downloadWillBegin) -> None:
        event_ = msg.get('params')
        event_["url"] = urlparse(event_["url"])._asdict()
        self.logEvent(
            msg = json.dumps(event_),
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
            msg = event_, 
            origin = "[File Chooser Opened]",
            debug = True
        )
        return None

class scriptParsedHandler(
    Handler, 
    interested_event = "Debugger.scriptParsed",
    output_events = ["[Script Loaded From Remote]", "[Script Alias From]"]
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
        _scheme = event_.get("url").get("scheme")
        if not (_scheme == 'https' or _scheme == 'http'):
            return None
        
        if event_.get("url"):
            self.m.update(
                "".join([event_.get('contentHash', ""), event_.get('url').get('netloc', "")]).encode()
            )
            event_['targetId'] = next(
                filter(
                    lambda x: x[1] == msg.get('sessionId'), 
                    self._target_session.items()
                ), 
                ("unknown", "")
            )[0]

            event_['originContentHash'] = self.m.hexdigest()
            self.logEvent(
                msg = json.dumps(event_),
                origin = "[Script Loaded From Remote]"
            )
            return None

        elif event_.get('stack'):
            """We do not discuss script execute script first.
            """
            return None
            url_ = event_.get('url')
            assert not url_, f"f{event_}"
            event_.pop("url")
            event_['stack']['callFrames'] = event_['stack']['callFrames'][0]
            event_['stack']['callFrames']['url'] = urlparse(url = event_.get('stack').get('callFrames').get('url'))._asdict()
            event_['stack']['callFrames'].pop('lineNumber')
            event_['stack']['callFrames'].pop('columnNumber')
        
            self.logEvent(
                msg = json.dumps(event_), 
                origin = "[Script Generated By Script]"
            )
        return None

class frameNavigatedHandler(
    Handler,
    interested_event = "Page.frameNavigated",
    output_events = ["[Frame Navigate To]"]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Page.frameNavigated) -> None:
        targetId: Types.Target.TargetID = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'),
                super()._target_session.items()
            )
        )[0]
        event_ = msg.get('params')
        extractedFrame = {
            "frameId": event_.get('frame').get('id'),
            "parentFrameId": event_.get('frame').get('parentId'),
            "url": urlparse(url = event_.get('frame').get('url'))._asdict(),
            "loaderId": event_.get('frame').get('loaderId'),
            "name": event_.get('frame').get('name'),
            "securityOrigin": event_.get('frame').get('securityOrigin'),
            "mimeType": event_.get('frame').get('mimeType')
        }
        event_["frame"] = extractedFrame
        event_["targetId"] = targetId
        self.logEvent(
            msg = json.dumps(event_),
            origin = "[Frame Navigate To]"
        )
        return None