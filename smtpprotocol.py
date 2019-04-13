import asyncio
import logging
from asyncio import StreamReaderProtocol, StreamReader, StreamWriter, Transport
from session import Session
from email._header_value_parser import get_addr_spec, get_angle_addr
from email.errors import HeaderParseError

log = logging.getLogger('mail.log')

'''
State machine:

start -> connection_made() [-> data_received() *] [-> eof_received() ?] -> connection_lost() -> end
'''
class SMTP(StreamReaderProtocol):
    def __init__(self, 
            hostname='localhost', 
            ident='Fake MTA',
            timeout=20,
            max_line_limit=5000):
        self.loop = asyncio.get_event_loop()
        self.hostname = hostname
        self.ident = ident
        self.timeout = timeout
        self.max_line_limit=max_line_limit

        self._timeout_coro = None
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
        self._reset_timeout()
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

    def _reset_timeout(self):
        if self._timeout_coro is not None:
            self._timeout_coro.cancel()

        self._timeout_coro = self.loop.call_later(
            self.timeout, self._timeout_cb
        )

    def _timeout_cb(self):
        log.info('{} connection timeout.'.format(self.session.peer))
        # transport.close will call self.connection_lost()
        self.transport.close()
        
    async def _handle_client(self):
        log.info('Handling connection from: {}'.format(self.session.peer))
        await self.push_status('200 {} {}'.format(self.hostname, self.ident))

        while self.transport is not None:
            try:
                line = await self._reader.readline()
                log.debug('Received line: {}'.format(line))
                line:str = line.rstrip(b'\r\n')
                if not line:
                    await self.push_status('500 Error: bad syntax')
                    continue

                if len(line) > self.max_line_limit:
                    await self.push_status('500 Error: line too long')
                    continue                    
                
                i = line.find(b' ')
                if i < 0:
                    try:
                        command = line.upper().decode(encoding='ascii')
                    except UnicodeDecodeError:
                        await self.push_status('500 Error: bad syntax')
                        continue
                    arg = None
                else:
                    try:
                        command = line[:i].upper().decode(encoding='ascii')
                    except UnicodeDecodeError:
                        await self.push_status('500 Error: bad syntax')
                    arg = line[i+1:]
                    try:
                        arg = str(arg, encoding='ascii', errors='strict')
                    except UnicodeDecodeError:
                        await self.push('500 Error: strict ASCII mode')
                        continue

                method = getattr(self, 'smtp_'+command, None)
                if method is None:
                    await self.push_status('500 Error: command not supported')
                    continue
                
                # reset timeout
                self._reset_timeout()
                await method(arg)

            except asyncio.CancelledError:
                self.transport.close()
                raise
            except Exception as e:
                await self.push_status('500 Error: unknown error.')

    async def push_status(self, status):
        resp = bytes(status + '\r\n', 'ascii')
        self._writer.write(resp)  
        await self._writer.drain()
        log.debug('Response sent: {}'.format(resp))

    async def smtp_HELO(self, hostname):
        if not hostname:
            await self.push_status('501 Syntax: HELO hostname')
        self.session.hostname = hostname
        await self.push_status('250 {}'.format(hostname))

    def _strip_command_keyword(self, arg:str, keyword:str):
        keyword_len = len(keyword)
        if arg[:keyword_len].upper() == keyword:
            return arg[keyword_len:].strip()
        return None

    def _getaddr(self, arg:str):
        if arg.lstrip().startswith('<'):
            addr, value = get_angle_addr(arg)
        else:
            addr, value = get_addr_spec(arg)
        try:
            addr = addr.addr_spec
        except:
            addr = None
        return addr, value 

    async def smtp_MAIL(self, arg):
        if not self.session.hostname:
            await self.push_status('503 Error: send HELO first')
            return
        errormsg = '501 Syntax: MAIL FROM: <address>'
        arg = self._strip_command_keyword(arg, 'FROM:')
        if arg is None:
            await self.push_status(errormsg)
            return
        addr, value = self._getaddr(arg)
        log.debug('The sender is {}, {}'.format(addr, value))
        
