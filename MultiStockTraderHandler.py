from StockTrader import StockTrader
from APIs.Trading_APIs.Trading212Api import Trading212Broker
from APIs.Stock_Data_APIs.YahooApi import Yahoo
from datetime import datetime
from MultiStockTraderInstance import MultiStockTradeStatus
import pandas as pd
import time
from SaveConfig import AppendStockTickerList, RemoveStockTickerList
from TickerValidation import ValidateTicker

class MultiStockTraderHandler:
    def __init__(self, stockTickers: list[str], safteyBalancePercent: float = -1.0, exchangeTimesUpdateIntervalSeconds: int = 86400, tradingLoopWaitSeconds: int = 600, stockDataInterval: str = "1h", stockDataPeriod: str = "1y",
                 instance: MultiStockTradeStatus = None):
        self.tradingState = instance
        self.stockTraders = {}
        self.traderRunHistory = {}
        self.stockApi = Yahoo()

        #Update Broker
        self.broker = Trading212Broker(
            paper_trading=True
        )

        if self.tradingState is not None:
            self.tradingState.UpdateData(
                CurrentBroker=self.broker.name
            )

        #Get Initial Balance
        self.safteyBalancePercent = safteyBalancePercent
        self.RefreshBalances(updateTraders=False)
        balancePerTrader = self.runTimeStartBalance / len(stockTickers)

        self.exchangeTimes = self.ThisWeekExchangeHours()
        self.timeSinceLastExchangeUpdate = 0
        self.exchangeTimesUpdateIntervalSeconds = exchangeTimesUpdateIntervalSeconds
        self.tradingLoopWaitSeconds = tradingLoopWaitSeconds

        #Check If Exchange Time Where Returned
        if self.exchangeTimes is None or len(self.exchangeTimes) == 0:
            print("Error: Has Not Received Any Exchange Hours. Trading Cannot Occur. Another Update Attempt Will Be Made In 30 Minutes.")
            self.timeSinceLastExchangeUpdate = self.exchangeTimesUpdateIntervalSeconds - 1800  # Next Update In 30 Minutes

        # Initialize a StockTrader instance for each ticker
        for ticker in stockTickers:
            self.stockTraders[ticker] = StockTrader(ticker=ticker, balance=balancePerTrader, benchmarkGraphs=False, broker=self.broker, 
                                                    stockMultiHandler=self, stockDataInterval=stockDataInterval, stockDataPeriod=stockDataPeriod, 
                                                    marketToTradeIn=self.GetExchangeFromTicker(ticker), stocksApi=self.stockApi)


    def RunUpdateLoop(self):
        while True:
            print(f"MultiStockTraderHandler Update Loop Running At {datetime.now().isoformat()}")

            if self.exchangeTimes is not None and len(self.exchangeTimes) > 0:
                for trader in self.stockTraders.values():
                    print(f"Running Trading Update Loop For {trader.ticker} At {datetime.now().isoformat()}")
                    trader.TradingUpdateLoop()
            else:
                print("Skipping Trading Update Loop As No Exchange Hours Are Available.")

            if self.tradingState is None:
                print("Trading Loop Result:")
                print(pd.DataFrame(self.traderRunHistory).T)
            else:
                self.tradingState.UpdateData(
                    LastUpdate=datetime.now().isoformat(),
                    Stocks = self.traderRunHistory
                )

            timeWaited = 0
            while timeWaited < self.tradingLoopWaitSeconds:
                #Check For Special Instructions
                if self.tradingState is not None:
                    specialInstructions = self.tradingState.GetAllInstructions()
                    
                    # Loop Through Each Ticker Addition/Removal Requests
                    for ticker in self.tradingState.SnapshotData().get("PendingStocks"):
                        tickerInfo = self.tradingState.SnapshotData().get("PendingStocks").get(ticker)

                        #Check If It Has Been Processed
                        if not tickerInfo.get("Processed"):
                            #Check Request Type
                            if tickerInfo.get("Remove"):
                                print(f"Removing Ticker {ticker}")
                                RemoveStockTickerList(ticker)

                                #Remove Ticker From Memory
                                if ticker in self.stockTraders:
                                    del self.stockTraders[ticker]

                                if ticker in self.traderRunHistory:
                                    del self.traderRunHistory[ticker]

                                print(f"Ticker {ticker} Removed From Trading List. Balance Will Be Redistributed On Next Update Loop.")
                            elif ValidateTicker(ticker, self.stockApi, self.broker):
                                # Make A New Trader With No Money
                                print(f"Adding New Ticker {ticker}")
                                self.stockTraders[ticker] = StockTrader(ticker=ticker, balance=0, benchmarkGraphs=False, broker=self.broker,
                                                                        stockMultiHandler=self, stockDataInterval="1h", stockDataPeriod="1y", marketToTradeIn=self.GetExchangeFromTicker(ticker), stocksApi=self.stockApi)
                                
                                # Update The Request
                                self.tradingState.UpdateStockStatus(ticker, "Added. Balance Assignment Pending.", False)

                                # Add The Ticker To The Config File
                                AppendStockTickerList(ticker)

                            else:
                                print(f"Ticker {ticker} Is Invalid. Skipping.")
                                self.tradingState.UpdateStockStatus(ticker, "Rejected. Invalid Ticker. Does Your Broker Need The Exchange Suffix?", True)

                    # Loop Through Each Ticker's Instructions
                    for ticker in specialInstructions:
                        if specialInstructions[ticker].get("backtest_requested", False):
                            print(f"Backtest Requested For {ticker}. Running Backtest")
                            self.stockTraders[ticker].UpdateStrategy()

                        if specialInstructions[ticker].get("optimiser_requested", False):
                            print(f"Optimiser Requested For {ticker}. Running Optimiser")
                            self.stockTraders[ticker].OptimizeTradingParameters()

                        if specialInstructions[ticker].get("config_updates", None) is not None:
                            print(f"Config Update Requested For {ticker}. Applying Config Updates: {specialInstructions[ticker]['config_updates']}")

                        self.tradingState.ClearStockInstructions(ticker)

                    
                time.sleep(1)
                timeWaited += 1
                self.timeSinceLastExchangeUpdate += 1
                
            #Check If Exchange Hours Need Updated
            if self.timeSinceLastExchangeUpdate >= self.exchangeTimesUpdateIntervalSeconds:
                print("Updating Exchange Hours...")
                self.UpdateExchangeHours()
                self.RefreshBalances(updateTraders=True)

    def ThisWeekExchangeHours(self):
        exhangeHours = self.broker.GetExchangeHours()
        returnResult = {}

        if(exhangeHours is not None):
            #Reformat Exhange Hours
            for exchange in exhangeHours:
                thisWeeksSchdules = []

                # Reformat Working Schdules
                for schedule in exchange.get("workingSchedules"):
                    for timeEvent in schedule.get("timeEvents"):
                        if timeEvent.get("type") in ("OPEN", "CLOSE", "AFTER_HOURS_OPEN"):
                            #See if its happening this week
                            date = datetime.fromisoformat(timeEvent.get("date").replace("Z", "+00:00"))

                            if(date.isocalendar().week == datetime.now().isocalendar().week):
                                thisWeeksSchdules.append({
                                    "type": timeEvent.get("type"),
                                    "date": date
                                })

                returnResult[exchange.get("name")] = thisWeeksSchdules

        return returnResult
    
    def UpdateExchangeHours(self):
        self.exchangeTimes = self.ThisWeekExchangeHours()

        if self.exchangeTimes is None or len(self.exchangeTimes) == 0:
            print("Error: Has Not Received Any Exchange Hours. Trading Cannot Occur. Another Update Attempt Will Be Made In 30 Minutes.")
            self.timeSinceLastExchangeUpdate = self.exchangeTimesUpdateIntervalSeconds - 1800  # Next Update In 30 Minutes
        else:
            self.timeSinceLastExchangeUpdate = 0

    def GetExchangeFromTicker(self, ticker: str) -> str:
        #Keep everything after the first underscore
        ticker = ticker.split("_", 1)[-1]
        
        if ticker == "US_EQ":
            return "NYSE"
    
    def IsExchangeOpen(self, exchange: str, time: datetime) -> bool:
        if exchange not in self.exchangeTimes:
            return False
    
        todaysSchedules = [schedule for schedule in self.exchangeTimes[exchange] if schedule.get("date").date() == time.date()]
        todaysSchedules.sort(key=lambda x: x.get("date"))

        isOpen = False
        for schedule in todaysSchedules:
            if schedule.get("type") == "OPEN" and schedule.get("date") <= time:
                isOpen = True
            elif schedule.get("type") == "CLOSE" and schedule.get("date") <= time:
                isOpen = False
            elif schedule.get("type") == "AFTER_HOURS_OPEN" and schedule.get("date") <= time:
                isOpen = False

        return isOpen
    
    def RefreshBalances(self, updateTraders: bool):
        self.balance = self.broker.GetAccountBalance(betaNetDepositTest=True)

        if self.balance is None:
            print("Error: Could Not Retrieve Account Balance. Cannot Start Traders.")
            quit()

        print(f"Account Balance To Distribute: ${self.balance:.2f}")

        # Check If Auto Saftey Balance Is Enabled
        if self.safteyBalancePercent < 0:
            self.safteyBalance = self.balance * 0.30  # Default To 70% Of Balance
        else:
            self.safteyBalance = self.balance * self.safteyBalancePercent

        # Check If Over 75% Of Capital Is Being Risked
        if(self.safteyBalance < (self.balance * 0.25)):
            print(f"Warning: You Are Risking Over 75% Of Your Capital By Setting A Saftey Balance Of ${self.safteyBalance:.2f}. This May Result In Bigger And More Impactful Losses. Remember:\nOnly Invest What You Can Afford To Lose...\nWe Are Not Responsible For Any Losses Incurred By Using This Bot.")

        self.runTimeStartBalance = self.balance - self.safteyBalance

        if self.runTimeStartBalance <= 0:
            print(f"Error: Saftey Balance Of ${self.safteyBalance:.2f} Is More Than Or Equal To Total Balance Of $1000.00. Cannot Start Traders.")
            quit()

        if updateTraders:
            #Split The Balance Equally Between All Traders
            balancePerTrader = self.runTimeStartBalance / len(self.stockTraders)

            # Update Each Trader's Balance
            for trader in self.stockTraders.values():
                trader.UpdateBalance(balancePerTrader)

                # Check If This Is A Pending Stock
                if trader.ticker in self.tradingState.SnapshotData().get("PendingStocks", {}):
                    #Rerun Backtest
                    trader.UpdateStrategy()

                    self.tradingState.RemovePendingStock(trader.ticker)