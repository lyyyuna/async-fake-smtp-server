class Session():
    def __init__(self, loop):
        self.loop = loop
        self.peer = None
        self.hostname = None
        self.mail_from = None
        self.rcpt_to = None
        self.data = None