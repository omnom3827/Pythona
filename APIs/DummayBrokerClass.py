import datetime
import dotenv
import os

env = dotenv.dotenv_values(".env")

# A Dummy Broker Class To Be Used As A Template For Creating New Broker Integrations
class DummyBroker:
    # api_key: str - This is the API Key For The Broker
    # api_secret: str - This is the API Secret For The Broker
    # paper_trading: bool - If True, The Broker Will Operate In Paper Trading Mode (No Real Money Is Used)
    # If Your Broker Uses Another Authentication Method Please Modify This Class. DO NOT CHANGE THE ARGS INTO THIS CLASS.
    # Please Be Very Careful Not To Expose Your API Keys/Secrets. You Should Use The .env File To Store Sensitive Information.
    def __init__(self, paper_trading=True):
        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.lastApiRequestTime = datetime.now()
        #Set this to whatever the broker's API cooldown time is (Seconds Between Requests) OR to space out requests to avoid rate limiting
        self.apiCooldown = 2

        if paper_trading:
            self.base_url = "https://demo.trading212.com/api/v0"
        else:
            self.base_url = "https://live.trading212.com/api/v0"

        self.authTestResult = self.Authenticate_Test()

    def Authenticate_Test(self):
        # This Method Test If You Can Authenticate With The Brokers API Correctly And Returns True/False Depending On Result
        raise NotImplementedError("Authenticate_Test Method Not Implemented Yet.")
    
    def PlaceOrder(self, ticker, limitPrice, amount):
        #This Method Places A Limit Buy Order And Return The Following Result:
        # {
        # "success": True | False (Did The Request Succeed)
        # "filled": True | False (Was The Order Filled Immediately)
        # "order_id": str (The Order ID Of The Placed Order)
        # }
        raise NotImplementedError("PlaceOrder Method Not Implemented Yet.")
        
    def CheckOrderStatus(self, order):
        # This Method Checks The Status Of An Order And Returns The Following Result:
        # {
        # "success": True | False (Did The Request Succeed)
        # "filled": True | False (Was The Order Filled)
        # "order_id": str (The Order ID Of The Placed Order)
        # "status": str (The Current Status Of The Order)
        # }
       raise NotImplementedError("CheckOrderStatus Method Not Implemented Yet.")

    def PlaceSellOrder(self, ticker, limitPrice, amount):
        #This Method Places A Stop Sell Order And Return The Following Result:
        # {
        # "success": True | False (Did The Request Succeed)
        # "filled": True | False (Was The Order Filled Immediately)
        # "order_id": str (The Order ID Of The Placed Order)
        # }
       raise NotImplementedError("PlaceSellOrder Method Not Implemented Yet.")
        
    def GetExchangeHours(self):
        # This Method Should Return Exchange Hours In The Following Format:
        # [Name E.g: NSEQ, {
        # "Date": datetime,
        # "Type": "OPEN" | "CLOSE"
        #}
        raise NotImplementedError("GetExchangeHours Method Not Implemented Yet.")
        
    def GetAccountBalance(self):
        # This Method Should Just Return An Account Balance NOT INCLUDING PENDING ORDERS!!
        # For Example: If You Have £1000 And An Active Buy Order Of £200, This Method Should Return £800
        raise NotImplementedError("GetAccountBalance Method Not Implemented Yet.")
    
    def GetOpenPositions(self, ticker):
        # This Method Gets The Open Positions For A Given Ticker And Returns The Following Format And Returns On Position. Using The ID 0:
        # {
        # "id": int (The Position ID ALWAYS 0),
        # "shares": float (The Number Of Shares Currently Held),
        # "price": float (The Average Price Paid Per Share)
        # }
        raise NotImplementedError("GetOpenPositions Method Not Implemented Yet.")
        
    def GetAllPendingOrders(self, ticker: str = None):
        #Gets all the pending order for a given ticker. If no ticker is provided get all pending orders.
        # Returns a dictionary of order_id to order details in the following format: [Order ID]: {
        #    "success": True | False (Did The Request Succeed)
        #    "ticker": str (The Ticker Of The Order)
        #    "filled": True | False (Was The Order Filled)
        #    "type": "BUY" | "SELL" (The Type Of The Order)
        #   }
        raise NotImplementedError("GetAllPendingOrders Method Not Implemented Yet.")