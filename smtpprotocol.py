import asyncio
import logging
from asyncio import StreamReaderProtocol, StreamReader, StreamWriter, Transport
from session import Session

log = logging.getLogger('mail.log')

'''
State machine:

start -> connection_made() [-> data_received() *] [-> eof_received() ?] -> connection_lost() -> end
'''
class SMTP(StreamReaderProtocol):
    def __init__(self, hostname='localhost', ident='Fake MTA'):
        self.loop = asyncio.get_event_loop()
        self.hostname = hostname
        self.ident = ident
        super().__init__(
            asyncio.StreamReader(loop=self.loop),
            client_connected_cb=self._client_connected_cb,
            loop=self.loop
        )

    def _client_connected_cb(self, reader:StreamReader, writer:StreamWriter):
        self._reader = reader
        self._writer = writer
        #log.info(self._writer)

    def connection_made(self, transport:Transport):
        self.session = Session(loop=self.loop)
        self.session.peer = transport.get_extra_info('peername')
        super().connection_made(transport)
        self.transport = transport
        log.info('Peer: {}'.format(self.session.peer))

        self._handle_coro_client = self.loop.create_task(
            self._handle_client()
        )

    def connection_lost(self, error):
        log.info('{} connection lost. {}'.format(self.session.peer, error))
        super().connection_lost(error)
        self._handle_coro_client.cancel()
        
    def eof_received(self):
        log.info('{} EOF received.'.format(self.session.peer))
        self._handle_coro_client.cancel()
        super().eof_received()
        
    async def _handle_client(self):
        log.info('Handling connection from: {}'.format(self.session.peer))
        await self.push_status('200 {} {}'.format(self.hostname, self.ident))

        while self.transport is not None:
            try:
                line = await self._reader.readline()
                log.debug('Received line: {}'.format(line))
                line = line.rstrip(b'\r\n')
                if not line:
                    await self.push_status('500 Error: bad syntax')
                    continue
            except asyncio.CancelledError:
                self.transport.close()
                raise
            except Exception as e:
                pass

    async def push_status(self, status):
        resp = bytes(status + '\r\n', 'ascii')
        self._writer.write(resp)  
        await self._writer.drain()
        log.debug('Response sent: {}'.format(resp))
