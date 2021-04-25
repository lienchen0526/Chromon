from typing import Literal, Tuple, TypedDict, Dict, Optional, Set, Union
import chrometypes as types
import uuid

ScriptInfo = TypedDict(
    "scriptinfo",
    {
        "domain": str,
        "contentHash": str
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
        "handler": str
    }
)

FrameScheduleInfo = TypedDict(
    "framescheduleinfo",
    {
        "reason": Literal["script", "http", "html", "user"]
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