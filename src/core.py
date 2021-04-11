import os, sys
from datetime import datetime
from asyncio.exceptions import InvalidStateError
import requests
import websocket
import time, json
import asyncio
import copy
from typing import Type, Union, List, Dict, Any, Optional

import chrometypes as Types

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
        print(f"[In {self.__class__.__name__}] run connectBrowser")
        self.connectBrowser()

    def connectBrowser(self) -> None:
        """Connect to Global debugee (Browser) itself
        """
        _endpoint = "/json/version"
        _rsp = requests.get(
            url = f"{self.debuggee_dest}{_endpoint}"
        )
        debugeeinfo: Types.Generic.GlobalDebugableInfo = json.loads(_rsp.text)

        self.ws = websocket.create_connection(
            url = debugeeinfo.get("webSocketDebuggerUrl")
        )
        self.ws.settimeout(self.wstimeout)
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
        """This function is a blocking call to send the obj as command to Debugee
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
        return _rply_obj

class Logger(object):
    
    def __init__(self, dir_: Optional[str] = None, username: Optional[str] = None, tag: Optional[str] = None, stdout: Optional[bool] = False) -> None:
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
        return None
        
    
    def log(self, origin: str, event: str) -> None:
        now = datetime.now().isoformat()
        msg = " - ".join([now, origin, event])
        if self.onlogging:
            print(msg, file = self.fs)
        if self.stdout:
            print(msg)
        return None

    def setLogFile(self, username: Optional[str] = None, tag: Optional[str] = None) -> None:
        """New log file

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
            print(f"[+ File already existed], appending...")
            if self.fs:
                self.fs.close()
            self.fs = open(full_path, "a")
            print(os.linesep + "=" * 50 + os.linesep, file = self.fs)
        else:
            print("[+ Log file not existed, Creating...]")
            if self.fs:
                self.fs.close()
            self.fs = open(full_path, "x")
    
    @property
    def disableLogging(self) -> bool:
        self.onlogging = False
        self.fs.flush()
        return self.onlogging

    @property
    def enableLogging(self) -> bool:
        self.onlogging = True
        return self.onlogging

    def __exit__(self):
        if self.fs:
            self.fs.close()

class CliCmd(object):
    _Cmd: dict = {
            "log": {
                "config": {
                    "show": None,
                    "set": None
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
            "exit": None
        }
    
    @classmethod
    def getScheme(cls):
        return copy.deepcopy(cls._Cmd)