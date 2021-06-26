from typing import Optional
import aiohttp
import asyncio
import ssl

class LogstachClient(object):
    
    def __init__(
        self, 
        hostname: str = "192.168.1.50", 
        port: int = 8080,
        ssl_: bool = False,
        verify: bool = False
    ) -> None:
        if not verify:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        self.url = "".join(["http", "s" if ssl_ else "", "://", hostname, str(port)])
        self.loop = asyncio.get_event_loop()
    
    async def startSession(self) -> None:
        pass