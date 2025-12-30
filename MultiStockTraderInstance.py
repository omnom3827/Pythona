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

        self.specialInstructions = {

        }

    def UpdateData(self, **kwargs):
        with self.lock:
            self.data.update(kwargs)

    def SnapshotData(self):
        with self.lock:
            return dict(self.data)
        
    def UpdateStockInstructions(self, ticker: str, dict: dict):
        with self.lock:
            if ticker not in self.specialInstructions:
                self.specialInstructions[ticker] = dict
            else:
                self.specialInstructions[ticker].update(dict)

    def ClearStockInstructions(self, ticker: str):
        with self.lock:
            if ticker in self.specialInstructions:
                del self.specialInstructions[ticker]

    def GetStockInstructions(self, ticker: str) -> dict:
        with self.lock:
            return self.specialInstructions.get(ticker, {})
        
    def GetAllInstructions(self) -> dict:
        with self.lock:
            return dict(self.specialInstructions)
