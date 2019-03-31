import asyncio
import logging
from smtpprotocol import SMTP


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('mail.log')

loop = asyncio.get_event_loop()
coro = loop.create_server(SMTP, '127.0.0.1', 5000)
server = loop.run_until_complete(coro)

#loop.add_signal_handler(signal.SIGINT, loop.stop)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()

loop.run_until_complete(server.wait_closed())
loop.close()