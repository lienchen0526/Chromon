import asyncio
import argparse

from core import ChromeBridge
import  chrometypes as Types
from handlers import Handler

class ChroMo(object):
    
    def __init__(self, args: argparse.Namespace):
        if not args.debugeehost:
            args.debugeehost = "localhost"
        if not args.debugeeport:
            args.debugeeport = 9222
        
        self.chrome = ChromeBridge(
            host = args.debugeehost,
            port = args.debugeeport
        )
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

async def main(args: argparse.Namespace):
    
    chromo = ChroMo(args = args)
    await asyncio.gather(chromo.entrypoint())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Chromo audit argument parser")
    parser.add_argument("-H","--debugeehost", type = str, help = "Debugee browser host address")
    parser.add_argument("-P", "--debugeeport", type = int, help = "Debugee browser host port")
    parser.add_argument("-t", "--tag", type = str, help = "Log tag for this audit worker")
    parser.add_argument("-u", "--username", type = str, help = "The username of the user using the browser")
    parser.add_argument("-d", "--logdir", type = str, help = "The directory that will store the audited event")
    args: argparse.Namespace = parser.parse_args()
    asyncio.run(main(args = args))