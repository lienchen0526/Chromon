from typing import Callable, Dict, Literal, Optional, Tuple, TypedDict, Union, List
import json
import asyncio
import hashlib
import copy
from urllib.parse import urlparse
import uuid
from copy import deepcopy

from core import ChromeBridge, Logger
import chromeevents as Events
import chrometypes as Types
from chromods import FrameStatus, FrameStatusPool, ScheduledNavigationPool, ScriptInfo

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

# Seal Done First
class TargetAttachedHandler(
    Handler, 
    interested_event = "Target.attachedToTarget", 
    output_events = [
        "[Main Frame Created]", 
        "[Sub-Frame Created]", 
        "[Frame Info Update to]"
    ]
):
    _INSTANCE = None
    def __init__(self) -> None:
        pass
    
    async def handle(self, msg: Events.Target.attachedToTarget) -> None:
        t: Types.Target.TargetInfo = msg.get('params').get('targetInfo')
        t['url'] = urlparse(url = t.get('url'))._asdict()
        t['targetSessionId'] = msg.get('params').get('sessionId')

        session_id = msg.get('params').get('sessionId')
        target_id = t.get('targetId')
        target_type = t.get('type')

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
            _msg['frameInfo'].pop('contactedDomains')
            _msg['frameInfo'].pop('scriptStatus')

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

                _msg['frameInfo'].pop('contactedDomains')
                _msg['frameInfo'].pop('scriptStatus')

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
            "scriptStatus": {}
        }
        async with self.frame_status_lock:
            self.frameStatusPool[t.get('targetId')] = frameStatus
        _msg = {
            "parentFrameUID": self.frameStatusPool.get(t.get('openerFrameId')),
            "frameUID": frameStatus.get('UID'),
            "frameId": t.get('targetId'),
            "frameInfo": deepcopy(frameStatus)
        }

        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')

        self.logEvent(
            msg = json.dumps(_msg),
            origin = "[Main Frame Created]" if frameStatus.get('mainFrame') else "[Sub-Frame Created]"
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

# Seal Done First    
class frameAttachedHandler(
    Handler, 
    interested_event = "Page.frameAttached",
    output_events = [
        "[Frame Attach to Frame]", 
        "[Script Create Sub-Frame]"
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Page.frameAttached) -> None:
        event_ = msg.get('params')
        targetId = event_.get('parentFrameId')

        backendTargetId: Types.Target.TargetID = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'),
                super()._target_session.items()
            )
        )[0]

        targetFrameStatus = deepcopy(self.frameStatusPool.get(targetId))
        if not targetFrameStatus:
            print(f"[+ Debugging] In {self.__class__.__name__} event, target frame not found in the frameId: {targetId}")
        
        frameStatus: FrameStatus = {
            "loaderId": None,
            "openerFrameUID": None,
            "title": None,
            "url": None,
            "mainFrame": None,
            "UID": uuid.uuid4().__str__(),
            "contactedDomains": set(),
            "scriptStatus": {}
        }
        self.frameStatusPool[event_.get('frameId')] = frameStatus

        stack_: Types.Runtime.StackTrace = event_.get('stack')

        if stack_:
            # Emit Script create subframe
            for callframe_ in stack_.get('callFrames'):
                scriptInfo: ScriptInfo = targetFrameStatus.get('scriptStatus').get(callframe_.get('scriptId'))
                if scriptInfo: break
            
            if not scriptInfo:
                backendTargetStatus = deepcopy(self.frameStatusPool.get(backendTargetId))
            
            for callframe_ in stack_.get('callFrames'):
                if scriptInfo: break
                scriptInfo: ScriptInfo = backendTargetStatus.get('scriptStatus').get(callframe_.get('scriptId'))
            
            stack_bottom = stack_.get('callFrames')[0]
            _msg = {
                "scriptDomainHash": ("/".join(
                    [
                        scriptInfo.get('domain'),
                        scriptInfo.get('contentHash')
                    ]) if scriptInfo else stack_bottom
                ),
                "frameUID": frameStatus.get('UID'),
                "frameId": event_.get('frameId')
            }
            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Script Create Sub-Frame]"
            )
        else:
            pass
        _msg = {
            "parentFrameUID": self.frameStatusPool.get(targetId).get('UID'),
            "parentFrameId": targetId,
            "frameUID": frameStatus.get('UID'),
            "frameId": event_.get('frameId'),
            "frameInfo": deepcopy(frameStatus)
        }
        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')

        self.logEvent(
            msg = json.dumps(_msg),
            origin = "[Frame Attach to Frame]"
        )
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
            msg = event_, 
            origin = "[File Chooser Opened]",
            debug = True
        )
        return None

# Seal Done First 
class scriptParsedHandler(
    Handler, 
    interested_event = "Debugger.scriptParsed",
    output_events = [
        "[Frame Execute Script]", 
        "[Script Initiate Remote Script]",
        "[Script Reference to]"
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
        event_['targetId'] = next(
            filter(
                lambda x: x[1] == msg.get('sessionId'), 
                self._target_session.items()
            ), 
            ("unknown", "")
        )[0]
        """
        1. If url exist: 
            i.   [Frame Execute Script] will be triggered.
            ii.  statusFramePool will add a script
        2. If stack exist: 
            i.   no event triggered.
            ii.  statusFramePool updated a script
        3. If both exist:
            i.   [Script initiate Remote Script] event triggered.
            ii.  [Frame Execute Script] will be triggered.
            ii.  statusFramePool will update a script 
        """
        tid = event_['targetId']
        sid = event_.get('scriptId')
        frameStatus = self.frameStatusPool.get(tid)
        if not frameStatus:
            print("[+ debugging] Error get frame status")

        if _scheme and event_.get('stack'):
            # Print Debugging information
            stack_bottom = event_.get('stack').get('callFrames')[-1]
            psid = stack_bottom.get('scriptId')
            if not (psinfo := (frameStatus.get('scriptStatus').get(stack_bottom.get('scriptId')))):
                print(f"[+ No parent script found] {event_}")
            async with self.frame_status_lock:
                self.frameStatusPool[tid]['scriptStatus'][sid] ={
                    "domain": event_.get('url').get('netloc', "Null"),
                    "contentHash": event_.get('contentHash', "")
                }
                # Emit [Script initiate Remote Script] Event
                try:
                    self.frameStatusPool[tid]['scriptStatus'][psid]['domain']
                except:
                    print(f"[+ debugging] tid: {tid}")
                    print(f"[+ debugging] psid: {psid}")
                _msg = {
                    "parentScript": {
                        "id": psid,
                        "domain": self.frameStatusPool[tid]['scriptStatus'][psid]['domain'],
                        "domainHash": "/".join(
                            [
                                self.frameStatusPool[tid]['scriptStatus'][psid]['domain'],
                                self.frameStatusPool[tid]['scriptStatus'][psid]['contentHash'],
                            ]
                        )
                    },
                    "childScript": {
                        "id": sid,
                        "domain": self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                        "domainHash": "/".join(
                            [
                                self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                                self.frameStatusPool[tid]['scriptStatus'][sid]['contentHash']
                            ]
                        )
                    }
                }
                _executionmsg = {
                    "frameUID": uid if (uid := (frameStatus.get('UID'))) else tid,
                    "Script": {
                        "id": sid,
                        "domain": self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                        "domainHash": "/".join(
                            [
                                self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                                self.frameStatusPool[tid]['scriptStatus'][sid]['contentHash']
                            ]
                        )
                    }
                }
            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Script Initiate Remote Script]"
            )
            self.logEvent(
                msg = json.dumps(_executionmsg),
                origin = "[Frame Execute Script]"
            )
            return None

        if _scheme:
            async with self.frame_status_lock:
                self.frameStatusPool[tid]['scriptStatus'][sid] ={
                    "domain": event_.get('url').get('netloc', "Null"),
                    "contentHash": event_.get('contentHash', "")
                }
                _executionmsg = {
                    "frameUID": uid if (uid := (frameStatus.get('UID'))) else tid,
                    "Script": {
                        "id": sid,
                        "domain": self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                        "domainHash": "/".join(
                            [
                                self.frameStatusPool[tid]['scriptStatus'][sid]['domain'],
                                self.frameStatusPool[tid]['scriptStatus'][sid]['contentHash']
                            ]
                        )
                    }
                }
            self.logEvent(
                msg = json.dumps(_executionmsg),
                origin = "[Frame Execute Script]"
            )
            return None
        if event_.get('stack'):
            stack_bottom = event_.get('stack').get('callFrames')[0]
            psid = stack_bottom.get('scriptId')
            if not (psid := (frameStatus.get('scriptStatus').get(stack_bottom.get('scriptId')))):
                print(f"[+ No parent script found] {event_}")
            async with self.frame_status_lock:
                self.frameStatusPool[tid]['scriptStatus'][sid] = self.frameStatusPool[tid]['scriptStatus'][psid]
                print(f"[+ Debugging] Add ScriptId: {sid} to targetId: {tid}")
            _msg = {
                "scriptId": sid,
                "frameUID": self.frameStatusPool[tid]['UID'],
                "frameId": tid,
                "referenceScriptId": psid
            }
            self.logEvent(
                msg = json.dumps(_msg),
                origin = "[Script Reference to]"
            )
            return None
        return None

# Seal Done First 
class frameNavigatedHandler(
    Handler,
    interested_event = "Page.frameNavigated",
    output_events = [
        "[Frame Navigate by Script]", 
        "[Frame Navigate by HTTP]", 
        "[Frame Navigate by HTML]", 
        "[Frame Navigate by User]"
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        self.initiator_map = {
            "user": "User",
            "http": "HTTP",
            "html": "HTML",
            "script": "Script"
        }
        return None
    
    async def handle(self, msg: Events.Page.frameNavigated) -> None:
        """
        1. Get navigation information from scheduledNavigations
        2. Delete item in scheduledNavigations
        2. Update frameStatusPool, ie. UID, contactedDomains, scriptStatus
        3. Emit [Frame Navigate by User/HTTP/HTML]
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
            # If frame become attachable, we may attach it asap.
            # So, `frameId` still dominent.
            pass

        originFrameStatus = deepcopy(self.frameStatusPool.get(frameId))
        if not originFrameStatus:
            print(f"[+ Debugging] In {self.__class__.__name__}, no original navigated frame found.")
        
        async with self.scheduled_navigation_lock:
            reasons = self.scheduledNavigations.pop(originFrameStatus.get('UID'), {"reason": "user"})
            if not reasons:
                print(f"[+ debugging] No navigation request for frame navigation: {originFrameStatus.get('UID')}")
                reasons = {
                    "reason": "user"
                }
        async with self.frame_status_lock:
            if not originFrameStatus:
                print(f"[+ Debugging] No origin frame found with frameId: {frameId}")
                return None
            self.frameStatusPool[frameId]['UID'] = uuid.uuid4().__str__()
            self.frameStatusPool[frameId]['contactedDomains'] = set()
            self.frameStatusPool[frameId]['scriptStatus'] = {}
            self.frameStatusPool[frameId]['url'] = urlparse(url = event_.get('url'))._asdict()
            self.frameStatusPool[frameId]['loaderId'] = event_.get('loaderId')

        _msg = {
            "frameUID": self.frameStatusPool[frameId]['UID'],
            "frameId": frameId,
            "originFrameUID": originFrameStatus.get('UID'),
            "originFrameId": frameId,
            "frameInfo": deepcopy(self.frameStatusPool[frameId])
        }
        _msg['frameInfo'].pop('contactedDomains')
        _msg['frameInfo'].pop('scriptStatus')

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
        
        if not frameUID:
            frameUID = event_.get('frameId')
            pass
        async with self.scheduled_navigation_lock:
            if self.scheduledNavigations.get(frameUID):
                return None
            
            self.scheduledNavigations[frameUID] = {
                "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "user",
                "disposition": None
            }
        return None

# Seal Done First 
class frameSheduledNavigationHandler(
    Handler,
    interested_event = "Page.frameScheduledNavigation",
    output_events = []
):
    _INSTANCE = None

    def __init__(self):
        self.reason_map = {
            "httpHeaderRefreash": "http",
            "scriptInitiated": "script",
            "metaTagRefresh": "html"
        }
        return None
    
    async def handle(self, msg: Events.Page.frameScheduledNavigation):
        event_ = msg.get('params')
        async with self.frame_status_lock:
            frameUID = self.frameStatusPool.get(event_.get('frameId')).get('UID')
        
        if not frameUID:
            frameUID = event_.get('frameId')
            pass
        async with self.scheduled_navigation_lock:
            if self.scheduledNavigations.get(frameUID):
                return None
            
            self.scheduledNavigations[frameUID] = {
                "reason": reason if (reason := (self.reason_map.get(event_.get('reason'), None))) else "user",
                "disposition": None
            }
        return None

class requestWillBeSentHandler(
    Handler,
    interested_event = "Network.requestWillBeSent",
    output_events = [
        "[Host Redirect to Host]",
        "[Script Request to Host]",
        "[Frame Request to Host]"
    ]
):
    _INSTANCE = None

    def __init__(self) -> None:
        return None
    
    async def handle(self, msg: Events.Network.requestWillBeSent) -> None:
        return None