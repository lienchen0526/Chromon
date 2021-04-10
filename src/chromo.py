import asyncio
import argparse
import sys

from core import ChromeBridge, Logger
import  chrometypes as Types
from handlers import Handler

class ChroMo(object):

    def __init__(self, args: argparse.Namespace):
        """This Module provide the interactive mechanism for user to
        manage element such as `Handler` and `ChromeBridge` and `Logger`.

        Args:
            args (argparse.Namespace): [description]
        """
        if not args.debugeehost:
            args.debugeehost = "localhost"
        if not args.debugeeport:
            args.debugeeport = 9222
        
        self.chrome = ChromeBridge(
            host = args.debugeehost,
            port = args.debugeeport
        )
        self.logger = Logger(
            dir_ = args.logdir,
            username = args.username,
            tag = args.tag
        )
        self.handler_host = Handler(
            interface = self.chrome,
            logger = self.logger
        )

    def attachToBrowser(self) -> None:
        _cmd: Types.Generic.DebugCommand = {
            "id": 1,
            "method": "Target.attachToBrowserTarget"
        }
        self.chrome.sendObj(_cmd)
        pass
    
    async def entrypoint(self) -> None:
        print(f"[In {self.__class__.__name__}] run attachToBrowser")
        self.attachToBrowser()
        print(f"[+ In {self.__class__.__name__}] attached success")
        asyncio.create_task(self.startCli())

        while True:
            msg = self.chrome.getReply()
            if msg:
                asyncio.create_task(self.handler_host.dispatch(msg))
            else:
                await asyncio.sleep(0)
                pass
        return None

    @staticmethod
    async def ainput(string: str) -> str:
        return await asyncio.get_event_loop().run_in_executor(
                None, lambda s=string: input(s+' '))
        return await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline)

    async def startCli(self) -> None:
        while True:
            raw_cmd = await self.ainput("cli>")
            print(raw_cmd)
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