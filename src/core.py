import os, sys
from datetime import datetime
from asyncio.exceptions import InvalidStateError
import requests
import websocket
import time, json
import asyncio
import copy
import aiohttp
import requests
from typing import Generator, Iterable, Type, Union, List, Dict, Any, Optional
import json
from functools import partial
from itertools import tee

import chrometypes as Types

class JSON(object):
    dumps = partial(json.dumps, default = lambda o: None)

class ChromeBridge(object):
    """
    This object implement the raw IO with debugging browser process
    """

    def __init__(self, host: str = "localhost", port: int = 9222, timeout: Union[int, float] = 0):
        """
        Args:
            host (str): IP or Hostname of the debugee browser
            port (int): port of the debugee browser
            timeout (int | float): second of the websocket for blocking function like WebSocket.recv
        """

        if not isinstance(host, str):
            raise TypeError(f"host should be an str, however, {type(host)} are detected")
        if not isinstance(port, int):
            raise TypeError(f"port argument should be int, however, {type(port)} are detected")
        if port < 0 or port > 65535:
            raise ValueError(f"invalid port number: {port}")
        if not (isinstance(timeout, int) or isinstance(timeout, float)):
            raise TypeError(f"invalid type of timeout as {type(timeout)}")
        if timeout < -1:
            raise ValueError(f"invalid value of timeout, timeout: {timeout} is smaller than 0")
        
        self.debuggee_dest = f"http://{host}:{port}"
        self.host = host
        self.port = port
        self.wstimeout = timeout
        self.coreQueue = asyncio.Queue()

        ready = False

        while not ready:
            try:
                _rsp: requests.Response = requests.head(
                    url = self.debuggee_dest
                )
                if _rsp.ok:
                    ready = True
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(1)
        print(f"[+ In {self.__class__.__name__}] run connectBrowser")
        self.connectBrowser()

    def connectBrowser(self) -> None:
        """Connect to Global debugee (Browser) itself
        """
        _endpoint = "/json/version"
        while True:
            try:
                _rsp = requests.get(
                    url = f"{self.debuggee_dest}{_endpoint}"
                )
                break
            except requests.exceptions.ConnectionError:
                time.sleep(3)

        debugeeinfo: Types.Generic.GlobalDebugableInfo = json.loads(_rsp.text)

        self.ws: websocket.WebSocket = websocket.create_connection(
            url = debugeeinfo.get("webSocketDebuggerUrl")
        )
        self.ws.settimeout(self.wstimeout)
        print(f"[+ In ChroMo] attach to browser success")
        return None

    def listTabs(self) -> List[Types.Generic.TabInfo]:
        """Return a List of tabInfo
        An example of a tab in the returned list will looks like:

        {
            "description": "",
            "devtoolsFrontednUrl": "/devtools/inspector.html?ws=localhost:9222/devtools/page/C8DC7AB21C62DB4F61C06B8F5626DDF8",
            "id": "C8DC7AB21C62DB4F61C06B8F5626DDF8",
            "title": "new tab",
            "type": "page" | "iframe" | "background_page",
            "url": "chrome://newtab/",
            "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/C8DC7AB21C62DB4F61C06B8F5626DDF8"
        }

        Returns:
            List[TabInfo]: A list of tabs information 
        """

        _endpoint = "/json"
        rsp = requests.get(f"{self.debuggee_dest}{_endpoint}")
        if rsp.ok:
            return json.loads(rsp.text)
        else:
            raise requests.exceptions.ConnectionError(f"Endpoint connection fail at debuggee host: {self.debuggee_dest}")
    
    def sendObj(self, obj: Types.Generic.DebugCommand) -> int:
        """This function is a non-blocking call to send the obj as command to Debugee
        Args:
            obj (dict): the DebugCommand object that can be dump to json

        Todo:
            Implement the blocking send command and receive from the send result
        """
        self.ws.send(
            payload = json.dumps(obj)
        )
        return obj.get('id')
    
    def getReply(self) -> Union[Dict["str", Any], None]:
        try:
            _msg = self.ws.recv()
            _rply_obj: Dict["str", Any] = json.loads(_msg)
        except BlockingIOError:
            _rply_obj = {}
        except websocket._exceptions.WebSocketConnectionClosedException:
            _rply_obj = {}
            self.connectBrowser()
        return _rply_obj
    
    def shutDown(self) -> bool:
        self.ws.close()
        return True

class Logger(object):
    
    def __init__(
        self, 
        dir_: Optional[str] = None, 
        username: Optional[str] = None, 
        tag: Optional[str] = None, 
        stdout: Optional[bool] = False, 
        strict_form: Optional[bool] = False,
        ifremote: Optional[bool] = False,
        **kwargs
    ) -> None:
        """Using `dir_` to specify the directory that the logging destination. 
        If `dir_` is not given, current working directory will be set.
        `stdout` will be used if `stdout` argument set to `True`.

        Args:
            dir_ (Optional[str]): path of the directory for log file.
            username (Optional[str]): `username` will be set to `default` if not set
            tag (Optional[str]): `tag` wil be set to `default` if not set.
            stdout (Optional[bool]): specify if display logged event to stdout.
        """
        super().__init__()
        self.stdout = stdout
        self.fs = None
        self.onlogging = True
        self.strict = strict_form
        self.ifremote = ifremote
        if dir_:
            if not isinstance(dir_, str):
                raise TypeError(f"dir_ should be type str, not {dir_}")
            self.logdir = dir_
        else:
            self.logdir = os.getcwd()
        
        if username:
            if not isinstance(username, str):
                raise TypeError("argument username should be a str")
            self.username = username
        else:
            self.username = "default"
        if tag:
            if not isinstance(tag, str):
                raise TypeError("argument tag should be a str")
            self.tag = tag
        else:
            self.tag = "default"
        
        if not os.path.exists(self.logdir):
            raise FileNotFoundError(f"directory not found: {self.logdir}")

        if not os.path.isdir(self.logdir):
            raise NotADirectoryError(f"{self.logdir} is not a directory")
        
        self.setLogFile(username = username, tag = tag)
        if ifremote:
            self.setLogRemote(kwargs)
            self.checkRemoteAlive()
        
        return None
        
    
    def log(self, origin: str, event: str, debug: Optional[bool] = False) -> None:
        if not self.onlogging:
            return None
        now = datetime.now().isoformat()
        if self.strict or self.ifremote:
            evt_num, evt_name = origin.split(" - ")
            structured_event: Dict[str, Any] = json.loads(event)
            structured_event = {
                "eventNumber": evt_num,
                "eventName": evt_name,
                "eventData": json.loads(event),
                "timestamp": now
            }
            if self.strict:
                event = json.dumps(structured_event)
            if self.ifremote:
                structured_event['fields'] = {}
                structured_event['fields']['hostname'] = self.username
                structured_event['fields']['logtag'] = self.tag
                asyncio.create_task(self.logToRemote(structured_event))
            
        msg = " - ".join([now, origin, event])
        print(msg, file = self.fs)

        if debug:
            print(msg)
        return None

    def setLogFile(self, username: Optional[str] = None, tag: Optional[str] = None) -> None:
        """New log file. It will close current file stream if file stream still
        opened. and open a new file stream.

        Args:
            username (Optional[str]): [description]
            tag (Optional[str]): [description]
        """
        if not username:
            username = "default"
        if not tag:
            tag = "default"
        
        if not isinstance(username, str):
            raise TypeError(f"username should be str, not {type(username)}")

        if not isinstance(tag, str):
            raise TypeError(f"tag should be str, not {type(tag)}")
        
        self.username = username
        self.tag = tag

        self.new_file = "".join([username, "-", tag, ".log"])
        full_path = os.path.join(self.logdir, self.new_file)

        if os.path.exists(full_path):
            print(f"[+ File already existed]: Appending...")
            if self.fs and not self.fs.closed:
                print(f"[+ Closing old file stream...]")
                self.fs.flush()
                self.fs.close()
            self.fs = open(full_path, "a")
            print(os.linesep + "=" * 50 + os.linesep, file = self.fs)
        else:
            print("[+ Log file not existed]: Creating...")
            if self.fs and not self.fs.closed:
                print(f"[+ Closing old file stream...]")
                self.fs.flush()
                self.fs.close()
            self.fs = open(full_path, "x")
    
    def setDirectory(self, dir_: str) -> int:
        if not isinstance(dir_, str):
            raise TypeError(f"dir_ is not a str, is {type(dir_)}")
        if not os.path.exists(dir_):
            print("[+ Specified directory path not exist]")
            return -1
        if not os.path.isdir(dir_):
            print("[+ Specified path is not a directory]")
            return -1
        if not self.username or not self.tag:
            raise AttributeError(f"Unknown Error due to not found attribute {'username' if not self.username else ''}, {'tag' if not self.tag else ''}")
        self.logdir = dir_

        return 0 if not self.setLogFile(username = self.username, tag = self.tag) else -1

    def setLogRemote(self, kwargs) -> None:
        scheme = kwargs.get('scheme', 'http')
        usessl = kwargs.get('usessl', False)
        host = kwargs.get('host', '192.168.50')
        port = kwargs.get('port', 8080)

        self.session = aiohttp.ClientSession()
        self.remote_url = "".join(
            [
                scheme,
                "s" if usessl else "",
                "://",
                host,
                ":" + str(port)
            ]
        )
        return None

    def checkRemoteAlive(self) -> None:
        if not self.remote_url:
            raise NotImplementedError(f"[In {self.__class__.__name__}]: remote url not exists")
        r = requests.head(self.remote_url)
        if r.ok:
            print(f"[In {self.__class__.__name__}]: Remote logging terminal health ok. Url: {self.remote_url}")
        else:
            print(f"[In {self.__class__.__name__}]: Remote logging terminal health not ok. Url: {self.remote_url}")
        return None

    async def logToRemote(self, msg: Dict[str, Any]) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(url = self.remote_url, data = json.dumps(msg)) as rsp:
                return rsp.ok

    @property
    def disableLogging(self) -> bool:
        self.onlogging = False
        self.fs.flush()
        return self.onlogging

    @property
    def enableLogging(self) -> bool:
        self.onlogging = True
        return self.onlogging

    async def shutDown(self) -> bool:
        if self.fs and not self.fs.closed:
            self.fs.close()
        if self.session and not self.session.closed:
            await self.session.close()
        return True

    def __exit__(self):
        if self.fs:
            self.fs.close()

class CliCmd(object):
    _Cmd: dict = {
            "log": {
                "config": {
                    "show": None,
                    "set": None,
                    "cd": None,
                    "strict": None
                },
                "pause": None,
                "start": None
            },
            "event": {
                "show": {
                    "active": None,
                    "all": None
                },
                "disable": None,
                "enable": None
            },
            "chrome": {
                "config": None
            },
            "memory": {
                "usage": None
            },
            "exit": None,
            "help": None
        }
    
    @classmethod
    def getScheme(cls):
        return copy.deepcopy(cls._Cmd)


def create_window(i: Iterable, window_size = 2):
    iters = tee(i, window_size)
    for i in range(1, window_size):
        for each in iters[i:]:
            next(each, None)
    return zip(*iters)