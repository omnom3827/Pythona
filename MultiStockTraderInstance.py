from threading import Lock

class MultiStockTradeStatus:
    def __init__(self):
        self.lock = Lock()
        self.data = {
            "LastUpdate": None,
            "CurrentBroker": None,
            "Stocks": {
            }
        }

    def Update(self, **kwargs):
        with self.lock:
            self.data.update(kwargs)

    def Snapshot(self):
        with self.lock:
            return dict(self.data)
