from dataclasses import dataclass
from typing import List
chromoEventList: List[str] = []

@dataclass
class MainFrameCreated:
    name: str = "[Main Frame Created]"