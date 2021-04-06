import requests
import websocket
import time, json
import asyncio
import copy
from typing import Union, List, Dict, Any
from queue import Queue
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
        print(f"[In {self.__class__}] run connectBrowser")
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
            '''
            if _rply_obj.get("method") == "Target.targetDestroyed":
                print(f"{json.dumps(_rply_obj)}")
            if _rply_obj.get("method") == "Target.attachedToTarget":
                peek_rply = copy.deepcopy(_rply_obj)
                peek_rply["params"]["targetId"] = peek_rply["params"]["targetInfo"]["targetId"]
                peek_rply["params"].pop("targetInfo")
                print(f"{json.dumps(peek_rply)}")
            if _rply_obj.get("method") == "Target.targetCreated":
                peek_rply = copy.deepcopy(_rply_obj)
                peek_rply["params"]["targetId"] = peek_rply["params"]["targetInfo"]["targetId"]
                peek_rply["params"].pop("targetInfo")
                print(f"{json.dumps(peek_rply)}")
                pass
            '''
        except BlockingIOError:
            _rply_obj = {}
        return _rply_obj