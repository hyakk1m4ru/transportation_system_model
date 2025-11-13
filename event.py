class Event:
    def __init__(self, time, event_type, func, *args):
        self.time = time
        self.type = event_type
        self.func = func
        self.args = args

    def __lt__(self, other):
        return self.time < other.time
