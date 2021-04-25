import chrometypes as Types
from typing import Type, TypedDict, Optional, Literal, Any, Union

class Target(object):
    targetCreated = TypedDict(
        "targetCreated",
        {
            "method": Literal["Target.targetCreated"],
            "params": TypedDict(
                "trgtCreate",
                {
                    "targetInfo": Types.Target.TargetInfo
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
            
        }
    )
    targetDestroyed = TypedDict(
        "targetDestroyed",
        {
            "method": Literal["Target.targetDestroyed"],
            "params": TypedDict(
                "trgtDestroy",
                {
                    "targetId": Types.Target.TargetID,
                    "sessionId": Optional[Types.Target.SessionID]
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )
    attachedToTarget = TypedDict(
        "attachedToTarget",
        {
            "method": Literal["Target.attachedToTarget"],
            "params": TypedDict(
                "trgtAttached",
                {
                    "sessionId": Types.Target.SessionID,
                    "targetInfo": Types.Target.TargetInfo,
                    "waitingForDebugger": bool
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )
    targetInfoChange = TypedDict(
        "targetInfoChange",
        {
            "method": Literal["Target.targetInfoChanged"],
            "sessionId": Optional[Types.Target.SessionID],
            "params": TypedDict(
                "changedTo",
                {
                    "targetInfo": Types.Target.TargetInfo
                }
            )
        }
    )

class Page(object):
    frameAttached = TypedDict(
        "frameAttached",
        {
            "method": Literal["Page.frameAttached"],
            "params": TypedDict(
                "frameinfo",
                {
                    "frameId": Types.Page.FrameId,
                    "parentFrameId": Types.Page.FrameId,
                    "stack": Types.Runtime.StackTrace
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )
    downloadWillBegin = TypedDict(
        "downloadWillBegin",
        {
            "method": Literal["Page.downloadWillBegin"],
            "params": TypedDict(
                "downloadwillbegin",
                {
                    "frameId": Types.Page.FrameId,
                    "guid": str,
                    "url": str,
                    "suggestedFilename": str
                } 
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )
    fileChooserOpened = TypedDict(
        "fileChooserOpened",
        {
            "method": Literal["Page.fileChooserOpened"],
            "params": TypedDict(
                "filechooseropened",
                {
                    "frameId": Types.Page.FrameId, # Experimental
                    "backendNodeId": Types.DOM.BackendNodeId,
                    "mode": Literal["selectSingle", "selectMultiple"]
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )
    frameNavigated = TypedDict(
        "frameNavigated",
        {
            "method": Literal["Page.frameNavigated"],
            "sessionId": Types.Target.SessionID,
            "params": TypedDict(
                "framenavigated",
                {
                    "frame": Types.Page.Frame,
                    "type": Types.Page.NavigationType
                }
            )
        }
    )
    documentOpened = TypedDict(
        "documentOpened",
        {
            "method": Literal["Page.documentOpened"],
            "sessionId": Types.Target.SessionID,
            "params": TypedDict(
                "documentopened",
                {
                    "frame": Types.Page.Frame
                }
            )
        }
    )
    frameRequestNavigation = TypedDict(
        "frameRequestNavigation",
        {
            "method": Literal["Page.frameRequestNavigation"],
            "sessionId": Types.Target.SessionID,
            "params": TypedDict(
                "framerequestnavigation",
                {
                    "frameId": Types.Page.FrameId,
                    "reason": Types.Page.ClientNavigationReason,
                    "url": str,
                    "disposition": Types.Page.ClientNavigationDisposition
                }
            )
        }
    )
    frameScheduledNavigation = TypedDict(
        "frameScheduledNavigation",
        {
            "method": Literal["Page.frameScheduledNavigation"],
            "sessionId": Types.Target.SessionID,
            "params": TypedDict(
                "frameshedulednavigation",
                {
                    "frameId": Types.Page.FrameId,
                    "delay": Union[int, float],
                    "reason": Types.Page.ClientNavigationReason,
                    "url": str
                }
            )
        }
    )

class Browser(object):
    downloadWillBegin = TypedDict(
        "downloadWillBegin",
        {
            "method": Literal["Browser.downloadWillBegin"],
            "params": TypedDict(
                "downloadwillbegin",
                {
                    "frameId": Types.Page.FrameId,
                    "guid": str,
                    "url": str,
                    "suggestedFilename": str
                } 
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )

class Debugger(object):
    scriptParsed = TypedDict(
        "scriptParsed",
        {
            "method": Literal["Debugger.scriptParsed"],
            "params": TypedDict(
                "scriptparsed",
                {
                    "scriptId": Types.Runtime.ScriptId,
                    "url": str, # [Script From Remote]
                    "startLine": int,
                    "startColumn": int,
                    "endLine": int,
                    "endColumn": int,
                    "executionContextId": Types.Runtime.ExecutionContextId,
                    "hash": str,
                    "executionContextAuxData": Optional[Any],
                    "isLiveEdit": Optional[bool], #Experimental
                    "sourceMapURL": Optional[str],
                    "hasSourceURL": Optional[bool],
                    "isModule": Optional[bool],
                    "length": int,
                    "stackTrace": Optional[Types.Runtime.StackTrace], # [Script Generated From]
                    "codeOffset": int, # Experimental
                    "scriptLanguage": Optional[Types.Debugger.ScriptLanguage], # Excperimental
                    "debugSymbols": Optional[Types.Debugger.DebugSymbols], # Experimental
                    "embedderName": Optional[str], # Experimental
                }
            ),
            "sessionId": Optional[Types.Target.SessionID]
        }
    )

class Network(object):
    requestWillBeSent = TypedDict(
        "requestWillBeSent",
        {
            "requestId": Types.Network.RequestId,
            "loaderId": Types.Network.LoaderId,
            "documentURL": str,
            "request": Types.Network.Request,
            "timestamp": Types.Network.MonotonicTime,
            "wallTime": Types.Network.TimeSinceEpoch,
            "initiator": Types.Network.Initiator,
            "redirectResponse": Optional[Types.Network.Response],
            "type": Optional[Types.Network.ResourceType],
            "frameId": Optional[Types.Page.FrameId],
            "hasUserGesture": Optional[bool]
        }
    )
    responseReceived = TypedDict(
        "responseReceived",
        {
            "requestId": Types.Network.RequestId,
            "loaderId": Types.Network.LoaderId,
            "timestamp": Types.Network.MonotonicTime,
            "type": Types.Network.ResourceType,
            "response": Types.Network.Response,
            "frameId": Optional[Types.Page.FrameId]
        }
    )