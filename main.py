import asyncio


class EchoServerProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        print('Connection from {}'.format(peername))
        self.transport = transport

    def data_received(self, data):
        message = data.decode()
        print('Data received {!r}'.format(message))
        self.transport.write(data)
        self.transport.close()


loop = asyncio.get_event_loop()
coro = loop.create_server(EchoServerProtocol, '127.0.0.1', 5000)
server = loop.run_until_complete(coro)

#loop.add_signal_handler(signal.SIGINT, loop.stop)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()

loop.run_until_complete(server.wait_closed())
loop.close()