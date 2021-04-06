import chrometypes as Types
from typing import TypedDict, Optional, Literal

class Target:
    targetCreated = TypedDict(
        "targetCreated",
        {
            "method": Literal["Target.targetCreated"],
            "params": TypedDict(
                "trgtCreate",
                {
                    "targetInfo": Types.Target.TargetInfo
                }
            )
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
            )
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
            )
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
    pass