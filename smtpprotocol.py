import asyncio
from asyncio import StreamReaderProtocol, StreamReader

'''
State machine:

start -> connection_made() [-> data_received() *] [-> eof_received() ?] -> connection_lost() -> end
'''
class SMTP(StreamReaderProtocol):
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        super().__init__(
            asyncio.StreamReader(loop=self.loop),
            client_connected_cb=self._client_connected_cb,
            loop=self.loop
        )

    def _client_connected_cb(self, reader, writer):
        self.reader = reader
        self.writer = writer

    def connection_made(self):
        
    def connection_lost(self):

    def eof_received(self):