from core import ChromeBridge
import  chrometypes as Types
from handlers import Handler
import asyncio

class ChroMo(object):
    
    def __init__(self):
        self.chrome = ChromeBridge()
        self.handler_host = Handler(interface = self.chrome)

    def attachToBrowser(self) -> None:
        _cmd: Types.Generic.DebugCommand = {
            "id": 1,
            "method": "Target.attachToBrowserTarget"
        }
        self.chrome.sendObj(_cmd)
        pass
    
    async def entrypoint(self) -> None:
        print(f"[In {self}] run attachToBrowser")
        self.attachToBrowser()
        print(f"[In {self}] attached success")
        while True:
            msg = self.chrome.getReply()
            if msg:
                asyncio.create_task(self.handler_host.dispatch(msg))
            else:
                await asyncio.sleep(0)
                pass
        return None

async def main():
    chromo = ChroMo()
    await asyncio.gather(chromo.entrypoint())

if __name__ == '__main__':
    asyncio.run(main())