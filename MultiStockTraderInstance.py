from threading import Lock

class MultiStockTradeStatus:
    def __init__(self):
        self.lock = Lock()
        self.data = {
            "LastUpdate": None,
            "CurrentBroker": None,
            "Stocks": {
            },
            "PendingStocks": {}
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
        
    def AddNewStock(self, ticker: str):
        with self.lock:
            if ticker not in self.data['Stocks']:
                if ticker not in self.data['PendingStocks']:
                    self.data['PendingStocks'][ticker] = {
                        "Processed": False,
                        "Rejected": False,
                        "Removed": False,
                        "Status": "Pending Addition"
                    }

    def RemoveStock(self, ticker: str):
        with self.lock:
            if ticker in self.data['Stocks']:
                del self.data['Stocks'][ticker]
            if ticker in self.data['PendingStocks']:
                del self.data['PendingStocks'][ticker]

    def UpdateStockStatus(self, ticker: str, status: str, rejected: bool):
        with self.lock:
            if ticker in self.data['PendingStocks']:
                self.data['PendingStocks'][ticker]['Status'] = status
                self.data['PendingStocks'][ticker]['Processed'] = True
                self.data['PendingStocks'][ticker]['Rejected'] = rejected

    def RemovePendingStock(self, ticker: str):
        with self.lock:
            if ticker in self.data['PendingStocks']:
                del self.data['PendingStocks'][ticker]
