from typing import Dict, List, TypedDict, Optional, Any, Literal
import enum

class Browser(object):
    BrowserContextID = str

class Network(object):
    LoaderId = str

class Page(object):
    FrameId = str
    AdFrameType = Literal['none', 'child', 'root']
    SecureContextType = Literal['Secure', 'SecureLocalhost', 'InsecureScheme', 'InsecureAncestor']
    CrossOriginIsolatedContextType = Literal\
    [
        'Isolated', 
        'NotIsolated', 
        'NotIsolatedFeatureDisabled'
    ]
    GatedAPIFeatures = Literal\
    [
        'SharedArrayBuffers', 
        'SharedArrayBuffersTransferAllowed', 
        'PerformanceMeasureMemory', 
        'PerformanceProfile'
    ]
    Frame = TypedDict(
        "Frame",
        {
            "id": FrameId,
            "parentId": Optional[str],
            "loaderId": Network.LoaderId,
            "name": Optional[str],
            "url": str,
            "urlFragment": Optional[str],
            "domainAndRegistry": str,
            "securityOrigin": str,
            "mimeType": str,
            "unreachableUrl": Optional[str],
            "adFrameType": Optional[AdFrameType],
            "secureContextType": SecureContextType,
            "crossOriginIsolatedContextType": CrossOriginIsolatedContextType,
            "gatedAPIFeatures": List[GatedAPIFeatures]
        }
    )
    FrameTree = TypedDict(
        "FrameTree",
        {
            "frame": Frame,
            "childFrames": Optional[list]
        }
    )
    NavigationType = Literal["Navigation", "BackForwardCacheRestore"]

class Target(object):
    TargetID = str # TargetID can be Page.FrameID.
    SessionID = str # The unique session identifier every debugged target connected by python
    ValidTypes = ('page', 'iframe', 'browser', 'script')

    TargetInfo = TypedDict(
        "TargetInfo",
        {
            "targetId": TargetID,
            "type": str,
            "title": str,
            "url": str,
            "attached": bool,
            "openerId": Optional[TargetID],
            "canAccessOpener": bool,
            "openerFrameId": Optional[Page.FrameId],
            "browserContextId": Optional[Browser.BrowserContextID]
        }
    )

class Runtime(object):
    UniqueDebuggerId = str
    ScriptId = str
    ExecutionContextId = str

    StackTraceId = TypedDict(
        "StackTraceId",
        {
            "id": str,
            "debuggerId": Optional[UniqueDebuggerId]
        }
    )
    CallFrame = TypedDict(
        "CallFrame",
        {
            "functionName": str,
            "scriptId": ScriptId,
            "url": str,
            "lineNumber": int,
            "columnNumber": int
        }
    )
    StackTrace = TypedDict(
        "StackTrace",
        {
            "description": Optional[str],
            "callFrames": List[CallFrame],
            "parent": Optional[dict],
            "parentId": StackTraceId
        }
    )
    pass

class Generic(object):

    TabInfo = TypedDict(
        "TabInfo",
        {
            "description": str,
            "devtoolsFrontendUrl": str,
            "id": str,
            "title": str,
            "url": str,
            "webSocketDebuggerUrl": str
        }
    )

    GlobalDebugableInfo = TypedDict(
        "GlobalDebugableInfo",
        {
            "Browser": str,
            "Protocol-Version": str,
            "User-Agent": str,
            "V8-Version": str,
            "Webkit-Version": str,
            "webSocketDebuggerUrl": str
        }
    )

    DebugCommand = TypedDict(
        "DebugCommand",
        {
            "id": Optional[int],
            "method": str,

            #This is used when using flatten mode. It specify the more accurate target method.
            "sessionId": Optional[Target.SessionID],
            "params": Optional[Dict[str, str]]
        }
    )

    DebugReply = TypedDict(
        "DebugReply",
        {
            # Message id `int` specified in DebugCommand, if you have.
            "id": int,
            
            # The <RETURN OBJECT> mentioned in Chrome Devtools Protocols
            "result": Dict[str, Any]
        }
    )

class DOM(object):
    BackendNodeId = int

class Debugger(object):
    ScriptLanguage = Literal["JavaScript", "WebAssembly"]
    DebugSymbols = TypedDict(
        "DebugSymbols",
        {
            "type": Literal["None", "SourceMap", "EmbededDWARF", "ExternalDWARF"],
            "externalURL": Optional[str]
        }
    )