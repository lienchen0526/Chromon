import asyncio
import argparse
from asyncio.exceptions import CancelledError
import sys, os
import yaml
import pyfiglet

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
        if args.yaml:
            with open(args.yaml) as fd:
                self.config: dict = yaml.safe_load(fd)
        
        if args.debugeehost:
            self.config['target']['debugeehost'] = args.debugeehost
        if args.debugeeport:
            self.config['target']['debugeeport'] = args.debugeeport
        if args.logdir:
            self.config['logging']['local']['dir'] = args.logdir
        if args.username:
            self.config['logging']['hostname'] = args.username
        if args.tag:
            self.config['logging']['tag'] = args.tag
        if args.strictlog:
            self.config['logging']['strict'] = args.strictlog
        
        self.chrome = ChromeBridge(
            host = self.config['target']['debugeehost'],
            port = self.config['target']['debugeeport']
        )
        self.logger = Logger(
            dir_ = self.config['logging']['local']['dir'],
            username = self.config['logging']['hostname'],
            tag = self.config['logging']['tag'],
            strict_form = self.config['logging']['strict'],
            ifremote = self.config.get("logging").get('enable_remote', False),
            **self.config.get('logging').get('remote')
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
    
    def registerCliFunction(self) -> None:
        self.clicmd['log']['config']['show'] = lambda slf=self:\
            print(f" +logging directory:  {slf.logger.logdir}{os.linesep} +log file name:      {slf.logger.new_file}{os.linesep} +file stream opened: {not slf.logger.fs.closed}{os.linesep} +logging paused:    {not slf.logger.onlogging}")
        self.clicmd['log']['config']['set'] = lambda lines, slf=self: slf.logger.setLogFile(**dict([x.split("=") for x in lines]))
        self.clicmd['log']['config']['cd'] = lambda lines, slf=self: slf.logger.setDirectory(lines[0]) if lines else print(f"[+ Please specify directory]")
        self.clicmd['log']['pause'] = lambda slf=self: slf.logger.disableLogging and print(f"{slf.logger.onlogging}")
        self.clicmd['log']['start'] = lambda slf=self: slf.logger.enableLogging and print(f"{slf.logger.onlogging}")
        self.clicmd['event']['show']['active'] = lambda slf=self: [print(" ".join((str(x[1]), x[0]))) for x in slf.handler_host._activedevent.items() if x[1] > 0]
        self.clicmd['event']['show']['all'] = lambda slf=self: [print(" ".join((str(x[1]) if x[1] > 0 else str(-x[1]), "disabled" if x[1] < 0 else "enabled ", x[0]))) for x in slf.handler_host._activedevent.items()]
        self.clicmd['event']['disable'] = lambda events,slf=self: [slf.handler_host.disableEvent(x) for x in events]\
            if not "all" in events else [slf.handler_host.disableEvent(x) for x in slf.handler_host._activedevent.keys()]
        self.clicmd['event']['enable'] = lambda events,slf=self: [slf.handler_host.enableEvent(x) for x in events]\
            if not "all" in events else [slf.handler_host.enableEvent(x) for x in slf.handler_host._activedevent.keys()]
        self.clicmd['exit'] = lambda slf=self: slf.logger.shutDown() and slf.chrome.shutDown() and asyncio.get_event_loop().stop() and exit(0)
        self.clicmd['help'] = lambda : print(f" +log config show/set [username=lien tag=chen]/cd <directory>{os.linesep} +log pause/start{os.linesep}{os.linesep} +event show active/all{os.linesep} +event enable/disable all/<sequenc of nums>{os.linesep} +exit")
        return None

    async def entrypoint(self) -> None:
        print(f"[+ In {self.__class__.__name__}] run attachToBrowser...")
        self.attachToBrowser()
        print(f"[+ In {self.__class__.__name__}] browser attaching success")

        tsk = asyncio.create_task(self.startCli())

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
            for id_, cell in enumerate(cmd_cells):
                if callable(cmd_scope):
                    cmd_scope(cmd_cells[id_:])
                    cmd_scope = None
                    break
                if cmd_scope is None:
                    print(f"[+ Invalid Command]")
                    break
                cmd_scope = cmd_scope.get(cell)
                pass
            if cmd_scope:
                if not callable(cmd_scope):
                    print(f"[+ Command Implement Error]")
                else:
                    cmd_scope()
        return None

async def main(args: argparse.Namespace):
    f = pyfiglet.Figlet()
    print(f.renderText("DSNS-Chromo"))
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
    parser.add_argument("-s", "--strictlog", type = bool, help = "Set if logging with json format output")
    parser.add_argument("-y", "--yaml", type = str, help = "Set yaml file if you have. Notice that argument may override yaml setting")
    args: argparse.Namespace = parser.parse_args()
    asyncio.run(main(args = args))