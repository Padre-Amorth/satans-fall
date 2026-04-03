class DummyGroup(list):
    def add(self, item):
        self.append(item)


class DummyPlayer:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
