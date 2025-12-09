import time
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import dotenv
import os

env = dotenv.dotenv_values(".env")

class Trading212Broker:
    def __init__(self, paper_trading=True):
        self.api_key = os.getenv("API_KEY")
        self.api_secret = os.getenv("API_SECRET")
        self.lastApiRequestTime = datetime.now()
        self.apiCooldown = 2

        if paper_trading:
            self.base_url = "https://demo.trading212.com/api/v0"
        else:
            self.base_url = "https://live.trading212.com/api/v0"

        self.authTestResult = self.Authenticate_Test()

    def Authenticate_Test(self):
        try:
            self.CheckForRateLimitCooldown()

            # Try running a request to test authentication
            result = requests.get(f"{self.base_url}/equity/history/orders", params={"limit": 2}, auth=HTTPBasicAuth(self.api_key, self.api_secret), timeout=10)

            self.lastApiRequestTime = datetime.now()

            #Check we got a 200 status code
            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(snippet)
                print(f"Authenticate_Test HTTP {result.status_code}: {snippet}")
                return False
            
        except Exception as e:
            print(f"Authentication Failed: {e}")
            return False
        
        print("Authentication Succeeded. We Can Connect To Trading212 API")
        return True
    
    def PlaceOrder(self, ticker, limitPrice, amount):
        if(self.authTestResult == False):
            print("Cannot Place Order: Authentication Test Failed.")
            return {
                "success": False
            }
        
        self.CheckForRateLimitCooldown()

        try:
            payload = {
                "limitPrice": limitPrice,
                "quantity": amount,
                "ticker": ticker,
                "timeValidity": "DAY",
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            result = requests.post(f"{self.base_url}/equity/orders/limit", json=payload, headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))
            # record the timestamp of this API request
            self.lastApiRequestTime = datetime.now()

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"PlaceOrder HTTP {result.status_code}: {snippet}")
                return {
                    "success": False,
                }

            # Check If Order Got Filled Immediately
            result = result.json()

            if result.get("filledQuantity") == result.get("quantity"):
                print("Order Filled Immediately.")
                return {
                    "success": True,
                    "filled": True,
                    "order_id": result.get("id")
                }
            else:
                print("Order Not Filled Immediately.")
                return {
                    "success": True,
                    "filled": False,
                    "order_id": result.get("id")
                }
            
        except Exception as e:
            print(f"PlaceOrder Failed: {e}")
            return {
                "success": False
            }
        
    def CheckOrderStatus(self, order):
        if(self.authTestResult == False):
            print("Cannot Check Order Status: Authentication Test Failed.")
            return {
                "success": False
            }
        
        self.CheckForRateLimitCooldown()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            result = requests.get(f"{self.base_url}/equity/orders/{order}", auth=HTTPBasicAuth(self.api_key, self.api_secret), headers=headers)

            self.lastApiRequestTime = datetime.now()

            #Check If Order Was Cancelled
            if(result.status_code == 404):
                print(f"Order #{order} Not Found (Possibly Cancelled).")
                return {
                    "success": True,
                    "filled": False,
                    "order_id": order,
                    "status": "CANCELLED"
                }

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"CheckOrderStatus HTTP {result.status_code}: {snippet}")
                return {
                    "success": False,
                }
            
            result = result.json()

            if result.get("filledQuantity") == result.get("quantity"):
                return {
                    "success": True,
                    "filled": True,
                    "order_id": result.get("id"),
                    "status": result.get("status")
                }
            else:
                return {
                    "success": True,
                    "filled": False,
                    "order_id": result.get("id"),
                    "status": result.get("status")
                }
            
        except Exception as e:
            print(f"CheckOrderStatus Failed: {e}")
            return {
                "success": False
            }

    def PlaceSellOrder(self, ticker, limitPrice, amount):
        if(self.authTestResult == False):
            print("Cannot Place Sell Order: Authentication Test Failed.")
            return {
                "success": False
            }
        
        self.CheckForRateLimitCooldown()

        payload = {
            "limitPrice": limitPrice,
            "quantity": -amount,
            "ticker": ticker,
            "timeValidity": "DAY",
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key
        }

        result = requests.post(f"{self.base_url}/equity/orders/limit", json=payload, headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

        self.lastApiRequestTime = datetime.now()

        if not (200 <= result.status_code < 300):
            snippet = (result.text or "").strip()[:500]
            print(f"PlaceSellOrder HTTP {result.status_code}: {snippet}")
            return {
                "success": False,
            }
        
        result = result.json()

        if result.get("filledQuantity") == result.get("quantity"):
            print("Sell Order Filled Immediately.")
            return {
                "success": True,
                "filled": True,
                "order_id": result.get("id")
            }
        else:
            print("Sell Order Not Filled Immediately.")
            return {
                "success": True,
                "filled": False,
                "order_id": result.get("id")
            }
        
    def GetExchangeHours(self):
        if(self.authTestResult == False):
            print("Cannot Get Exchange Hours: Authentication Test Failed.")
            return None
        
        self.CheckForRateLimitCooldown()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            result = requests.get(f"{self.base_url}/equity/metadata/exchanges", headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

            self.lastApiRequestTime = datetime.now()

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"GetExchangeHours HTTP {result.status_code}: {snippet}")
                return None
            
            return result.json()
        except Exception as e:
            print(f"GetExchangeHours Failed: {e}")
            return None
        
    def GetAccountBalance(self):
        if(self.authTestResult == False):
            print("Cannot Get Account Balance: Authentication Test Failed.")
            return None
        
        self.CheckForRateLimitCooldown()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            result = requests.get(f"{self.base_url}/equity/account/summary", headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

            self.lastApiRequestTime = datetime.now()

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"GetAccountBalance HTTP {result.status_code}: {snippet}")
                return None

            result = result.json()
            return result.get("cash").get("availableToTrade") + result.get("cash").get("reservedForOrders")
        except Exception as e:
            print(f"GetAccountBalance Failed: {e}")
            return None
        
    def GetOpenPositions(self, ticker):
        if(self.authTestResult == False):
            print("Cannot Get Open Positions: Authentication Test Failed.")
            return None
        
        self.CheckForRateLimitCooldown()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            query = {
                "ticker": ticker
            }

            result = requests.get(f"{self.base_url}/equity/positions", params=query, headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

            self.lastApiRequestTime = datetime.now()

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"GetOpenPositions HTTP {result.status_code}: {snippet}")
                self.lastApiRequestTime = datetime.now()
                return None

            result = result.json()

            print(result)
            
            return {
                "id": 0,
                "shares": result[0].get("quantityAvailableForTrading"),
                "price": result[0].get("averagePricePaid"),
            }
        except Exception as e:
            print(f"GetOpenPositions Failed: {e}")
            return None
        
    def GetAllPendingOrders(self, ticker: str = None):
        if(self.authTestResult == False):
            print("Cannot Get All Pending Orders: Authentication Test Failed.")
            return None
        
        self.CheckForRateLimitCooldown()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            result = requests.get(f"{self.base_url}/equity/orders", headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

            self.lastApiRequestTime = datetime.now()

            if(not (200 <= result.status_code < 300)):
                snippet = (result.text or "").strip()[:500]
                print(f"GetAllPendingOrders HTTP {result.status_code}: {snippet}")
                return None

            json_result = result.json()

            allOrders = {}

            print(json_result)

            for order in json_result:     
                if(ticker is not None and ticker != order.get("instrument").get("ticker")):
                    continue

                allOrders[order.get("id")] = {
                    "success": True,
                    "ticker": order.get("instrument").get("ticker"),
                    "filled": False,
                    "type": order.get("type"),
                }

            return allOrders
        except Exception as e:
            print(f"GetAllPendingOrders Failed: {e}")
            return None
        
    def CheckForRateLimitCooldown(self):
        # Check if last request was within the cooldown period
        elapsed = (datetime.now() - self.lastApiRequestTime).total_seconds()
        if elapsed < self.apiCooldown:
            remaining = self.apiCooldown - elapsed
            print(f"Waiting for API Cooldown: {int(remaining)} seconds")
            time.sleep(remaining if remaining > 0 else 0)