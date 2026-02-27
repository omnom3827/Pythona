import os
import json

def AppendStockTickerList(newTicker):
    #Check If Config Directory Exists
    if not os.path.exists("Config"):
        os.makedirs("Config", exist_ok=True)
    
    if(os.path.exists("Config/StockTickers.json")):
        #Read The Current Ticker List
        with open('Config/StockTickers.json', 'r') as f:
            tickerList = json.load(f)

        #Append The New Ticker To The List If It Does Not Already Exist
        if newTicker not in tickerList:
            print(f"Appending Stock Ticker {newTicker} To Config File (StockTickers.json)")
            tickerList.append(newTicker)

            with open("Config/StockTickers.json", "w") as f:
                json.dump(tickerList, f, indent=4)
    else:
        print(f"Cannot Append Stock Ticker {newTicker} As Config File (StockTickers.json) Does Not Exist. Creating New Config File With Stock Ticker {newTicker}")

        tickerList = [newTicker]

        with open("Config/StockTickers.json", "w") as f:
            json.dump(tickerList, f, indent=4)

def RemoveStockTickerList(ticker):
    #Try To Read The Current Ticker List
    if(os.path.exists("Config/StockTickers.json")):
        print(f"Removing Ticker {ticker} From Config File (StockTickers.json)")
        with open('Config/StockTickers.json', 'r') as f:
            tickerList = json.load(f)
        
        if ticker in tickerList:
            tickerList.remove(ticker)

            with open("Config/StockTickers.json", "w") as f:
                json.dump(tickerList, f, indent=4)
    else:
        print(f"Cannot Remove Stock Ticker {ticker} As Config File (StockTickers.json) Does Not Exist.")

def LoadFromConfig() -> dict:
    fullConfig = {}

    #Try To Load Stock Tickers
    if(os.path.exists("Config/StockTickers.json")):
        with open('Config/StockTickers.json', 'r') as f:
            tickerList = json.load(f)
        
        fullConfig["stockTickers"] = tickerList
    else:
        print("No Stock Tickers Loaded From Config As It Does Not Exist. Using Default Ticker (AAPL_US_EQ)")
        fullConfig["stockTickers"] = ["AAPL_US_EQ"]

        #Create Config File With Default Ticker
        AppendStockTickerList("AAPL_US_EQ")
   
    return fullConfig