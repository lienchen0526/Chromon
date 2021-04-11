import asyncio
import argparse
from asyncio.exceptions import CancelledError
import sys, os

from core import ChromeBridge, Logger, CliCmd
import  chrometypes as Types
from handlers import Handler

class ChroMo(object):

    def __init__(self, args: argparse.Namespace):
        """This Module provide the interactive mechanism for user to
        manage element such as `Handler` and `ChromeBridge` and `Logger`.

        Args:
            args (argparse.Namespace): argument got from main function
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
        self.clicmd = CliCmd.getScheme()

    def attachToBrowser(self) -> None:
        _cmd: Types.Generic.DebugCommand = {
            "id": 1,
            "method": "Target.attachToBrowserTarget"
        }
        self.chrome.sendObj(_cmd)
        pass
    
    def registerCliFunction(self):
        self.clicmd['log']['config']['show'] = lambda slf=self:\
            print(f"logging directory:  {slf.logger.logdir}{os.linesep}log file name:      {slf.logger.new_file}{os.linesep}file stream opened: {slf.logger.fs.closed}")
        self.clicmd['log']['config']['set'] = lambda lines, slf=self: slf.logger.setLogFile(**dict([x.split("=") for x in lines]))
        self.clicmd['log']['pause'] = lambda slf=self: slf.logger.disableLogging and print(f"{slf.logger.onlogging}")
        self.clicmd['log']['start'] = lambda slf=self: slf.logger.enableLogging and print(f"{slf.logger.onlogging}")
        self.clicmd['event']['show']['active'] = lambda slf=self: [print(" ".join((str(x[1]), x[0]))) for x in slf.handler_host._activedevent.items() if x[1] > 0]
        self.clicmd['event']['show']['all'] = lambda slf=self: [print(" ".join((str(x[1]) if x[1] > 0 else str(-x[1]), "disabled" if x[1] < 0 else "enabled ", x[0]))) for x in slf.handler_host._activedevent.items()]
        self.clicmd['event']['disable'] = lambda events,slf=self: [slf.handler_host.disableEvent(x) for x in events]\
            if not "all" in events else [slf.handler_host.disableEvent(x) for x in slf.handler_host._activedevent.keys()]
        self.clicmd['event']['enable'] = lambda events,slf=self: [slf.handler_host.enableEvent(x) for x in events]\
            if not "all" in events else [slf.handler_host.enableEvent(x) for x in slf.handler_host._activedevent.keys()]
        self.clicmd['exit'] = exit
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

    async def startCli(self) -> None:
        self.registerCliFunction()
        while True:
            raw_cmd = await self.ainput("cli>")
            cmd_cells = raw_cmd.split(" ")
            cmd_scope = self.clicmd
            for cell in enumerate(cmd_cells):
                if callable(cmd_scope):
                    cmd_scope(cmd_cells[cell[0]:])
                    cmd_scope = None
                    break
                if cmd_scope is None:
                    print(f"[+ Invalid Command]")
                    break
                cmd_scope = cmd_scope.get(cell[1])
                pass
            if cmd_scope:
                if not callable(cmd_scope):
                    print(f"[+ Command Implement Error]")
                else:
                    cmd_scope()
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