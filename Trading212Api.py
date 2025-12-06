import time
import requests
from requests.auth import HTTPBasicAuth

class Trading212Broker:
    def __init__(self, api_key, api_secret, paper_trading=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.apiCooldown = 2
        self.currentCooldown = 0

        if paper_trading:
            self.base_url = "https://demo.trading212.com/api/v0"
        else:
            self.base_url = "https://live.trading212.com/api/v0"

        self.authTestResult = self.Authenticate_Test()

    def Authenticate_Test(self):
        try:
            #Check if we need to wait due to cooldown
            if self.currentCooldown > 0:
                print(f"Waiting for API Cooldown: {self.currentCooldown} seconds")
                time.sleep(self.currentCooldown)
                self.currentCooldown = 0

            # Try running a request to test authentication
            result = requests.get(f"{self.base_url}/equity/history/orders", params={"limit": 2}, auth=HTTPBasicAuth(self.api_key, self.api_secret), timeout=10)

            #Check we got a 200 status code
            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(result.text)
                print(f"Authenticate_Test HTTP {result.status_code}: {snippet}")
                self.currentCooldown = self.apiCooldown
                return False
            
            self.currentCooldown = self.apiCooldown
            
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
        
        if self.currentCooldown > 0:
            print(f"Waiting for API Cooldown: {self.currentCooldown} seconds")
            time.sleep(self.currentCooldown)
            self.currentCooldown = 0

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

            if not (200 <= result.status_code < 300):
                snippet = (result.text or "").strip()[:500]
                print(f"PlaceOrder HTTP {result.status_code}: {snippet}")
                self.currentCooldown = self.apiCooldown
                return {
                    "success": False,
                }

            # Check If Order Got Filled Immediately
            order_response = result.json()

            self.currentCooldown = self.apiCooldown

            if order_response.get("filledQuantity") == order_response.get("quantity"):
                print("Order Filled Immediately.")
                return {
                    "success": True,
                    "filled": True,
                    "order_id": order_response.get("id")
                }
            else:
                print("Order Not Filled Immediately.")
                return {
                    "success": True,
                    "filled": False,
                    "order_id": order_response.get("id")
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
        
        if self.currentCooldown > 0:
            print(f"Waiting for API Cooldown: {self.currentCooldown} seconds")
            time.sleep(self.currentCooldown)
            self.currentCooldown = 0

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_key
            }

            response = requests.get(f"{self.base_url}/equity/orders/{order}", auth=HTTPBasicAuth(self.api_key, self.api_secret), headers=headers)

            #Check If Order Was Cancelled
            if(response.status_code == 404):
                print(f"Order #{order} Not Found (Possibly Cancelled).")
                self.currentCooldown = self.apiCooldown
                return {
                    "success": True,
                    "filled": False,
                    "order_id": order,
                    "status": "CANCELLED"
                }

            if not (200 <= response.status_code < 300):
                snippet = (response.text or "").strip()[:500]
                print(f"CheckOrderStatus HTTP {response.status_code}: {snippet}")
                self.currentCooldown = self.apiCooldown
                return {
                    "success": False,
                }
            
            order_info = response.json()
            self.currentCooldown = self.apiCooldown
            print(order_info)

            if order_info.get("filledQuantity") == order_info.get("quantity"):
                print("Order Has Been Filled.")
                return {
                    "success": True,
                    "filled": True,
                    "order_id": order_info.get("id"),
                    "status": order_info.get("status")
                }
            else:
                print("Order Has Not Been Filled Yet.")
                return {
                    "success": True,
                    "filled": False,
                    "order_id": order_info.get("id"),
                    "status": order_info.get("status")
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
        
        if self.currentCooldown > 0:
            print(f"Waiting for API Cooldown: {self.currentCooldown} seconds")
            time.sleep(self.currentCooldown)
            self.currentCooldown = 0

        payload = {
            "stopPrice": limitPrice,
            "quantity": -amount,
            "ticker": ticker,
            "timeValidity": "DAY",
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key
        }

        result = requests.post(f"{self.base_url}/equity/orders/stop", json=payload, headers=headers, auth=HTTPBasicAuth(self.api_key, self.api_secret))

        if not (200 <= result.status_code < 300):
            snippet = (result.text or "").strip()[:500]
            print(f"PlaceSellOrder HTTP {result.status_code}: {snippet}")
            self.currentCooldown = self.apiCooldown
            return {
                "success": False,
            }
        
        sell_response = result.json()
        self.currentCooldown = self.apiCooldown

        if sell_response.get("filledQuantity") == sell_response.get("quantity"):
            print("Sell Order Filled Immediately.")
            return {
                "success": True,
                "filled": True,
                "order_id": sell_response.get("id")
            }
        else:
            print("Sell Order Not Filled Immediately.")
            return {
                "success": True,
                "filled": False,
                "order_id": sell_response.get("id")
            }