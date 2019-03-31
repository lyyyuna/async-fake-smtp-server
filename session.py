class Session():
    def __init__(self, loop):
        self.loop = loop
        self.peer = None
        self.hostname = None