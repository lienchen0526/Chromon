from asyncio import events
from typing import List, Literal, Tuple, TypedDict, Dict, Optional, Set, Union

from cdp.target import SessionID
from chromeevents import Network
import chrometypes as types
import chromeevents as event
import uuid

StructuredUrl = TypedDict(
    "url",
    {
        "scheme": str,
        "netloc": str,
        "path": str,
        "params": str,
        "query": str,
        "fragment": str
    }
)

NetworkSession = TypedDict(
    "networksession",
    {
        "request": Optional[types.Network.Request],
        "response": Optional[types.Network.Response]
    }
)

NetworkInfo = TypedDict(
    "networkinfo",
    {
        "session": List[NetworkSession],
        "bornTime": float
    }
)

ScriptInfo = TypedDict(
    "scriptinfo",
    {
        "domain": str,
        "url": Optional[StructuredUrl],
        "contentHash": str,
        "contactedDomains": Set[str],
        "httpGetUrls": Set[str],
        "callScriptHistory": Set[str],
        "spawnScriptHistory": Set[str]
    }
)

FrameScheduleInfo = TypedDict(
    "framescheduleinfo",
    {
        "onScheduling": bool,
        "reason": Literal["script", "http", "html", "user"],
        "destinationUrl": Union[str, None],
        "script": Union[ScriptInfo, None]
    }
)

FrameStatus = TypedDict(
    "framestatus",
    {
        "loaderId": Optional[types.Network.LoaderId],
        "openerFrameUID": Union[str, types.Page.FrameId],
        "title": Union[str, Tuple[str]],
        "url": dict,
        "mainFrame": bool,
        "UID": uuid.UUID,
        "contactedDomains": Set[str],
        "scriptStatus": Dict[types.Runtime.ScriptId, ScriptInfo],
        "handler": str,
        "networkSessions": Dict[types.Network.RequestId, NetworkInfo],
        "navigationStatus": FrameScheduleInfo
    }
)

FrameStatusPool = Dict[
    types.Page.FrameId,
    FrameStatus
]

ScheduledNavigationPool = Dict[
    uuid.UUID,
    FrameScheduleInfo
]