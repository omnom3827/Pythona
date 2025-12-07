from StockTrader import StockTrader
from Trading212Api import Trading212Broker
import dotenv
import os
from datetime import datetime
import time

env = dotenv.dotenv_values(".env")

class MultiStockTraderHandler:
    def __init__(self, stockTickers: list[str], minBalancePerTrader: float = 100.0, safteyBalancePercent: float = -1.0, exchangeTimesUpdateIntervalSeconds: int = 86400, tradingLoopWaitSeconds: int = 60):
        self.stockTraders = {}
        self.broker = Trading212Broker(
            api_key=os.getenv("API_KEY"),
            api_secret=os.getenv("API_SECRET"),
            paper_trading=True
        )

        self.balance = self.broker.GetAccountBalance()

        if self.balance is None:
            print("Error: Could Not Retrieve Account Balance. Cannot Start Traders.")
            return

        print(f"Account Balance To Distribute: ${self.balance:.2f}")

        # Check If Auto Saftey Balance Is Enabled
        if safteyBalancePercent < 0:
            self.safteyBalance = self.balance * 0.70  # Default To 70% Of Balance
        else:
            self.safteyBalance = self.balance * safteyBalancePercent

        # Check If Over 75% Of Capital Is Being Risked
        if(self.safteyBalance < (self.balance * 0.25)):
            print(f"Warning: You Are Risking Over 75% Of Your Capital By Setting A Saftey Balance Of ${self.safteyBalance:.2f}. This May Result In Bigger And More Impactful Losses. Remember:\nOnly Invest What You Can Afford To Lose...\nWe Are Not Responsible For Any Losses Incurred By Using This Bot.")

        self.runTimeStartBalance = self.balance - self.safteyBalance

        if self.runTimeStartBalance <= 0:
            print(f"Error: Saftey Balance Of ${self.safteyBalance:.2f} Is More Than Or Equal To Total Balance Of $1000.00. Cannot Start Traders.")
            return

        self.exchangeTimes = self.ThisWeekExchangeHours()
        self.timeSinceLastExchangeUpdate = 0
        self.exchangeTimesUpdateIntervalSeconds = exchangeTimesUpdateIntervalSeconds
        self.tradingLoopWaitSeconds = tradingLoopWaitSeconds

        #Check If Exchange Time Where Returned
        if self.exchangeTimes is None or len(self.exchangeTimes) == 0:
            print("Error: Has Not Received Any Exchange Hours. Trading Cannot Occur. Another Update Attempt Will Be Made In 30 Minutes.")
            self.timeSinceLastExchangeUpdate = self.exchangeTimesUpdateIntervalSeconds - 1800  # Next Update In 30 Minutes

        #Split The Balance Equally Between All Traders
        balancePerTrader = self.runTimeStartBalance / len(stockTickers)

        if balancePerTrader < minBalancePerTrader:
            print(f"Warning: Each Trader Will Only Have ${balancePerTrader:.2f}. Which Is Below Your Set Minimum Of ${minBalancePerTrader:.2f} Per Trader.\nThis May Result In Failed Orders Due To Insufficient Funds. Please Monitor.")
        
        # Initialize a StockTrader instance for each ticker
        for ticker in stockTickers:
            self.stockTraders[ticker] = StockTrader(ticker=ticker, balance=balancePerTrader, benchmarkGraphs=False, broker=self.broker, stockMultiHandler=self)
        

        while True:
            print(f"MultiStockTraderHandler Update Loop Running At {datetime.now().isoformat()}")

            if self.exchangeTimes is not None and len(self.exchangeTimes) > 0:
                for trader in self.stockTraders.values():
                    print(f"Running Trading Update Loop For {trader.ticker} At {datetime.now().isoformat()}")
                    trader.TradingUpdateLoop()
            else:
                print("Skipping Trading Update Loop As No Exchange Hours Are Available.")

            time.sleep(self.tradingLoopWaitSeconds)  # Wait for specified seconds before the next update loop

            #Check If Exchange Hours Need Updated
            if self.timeSinceLastExchangeUpdate >= self.exchangeTimesUpdateIntervalSeconds:
                print("Updating Exchange Hours...")
                self.UpdateExchangeHours()

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
                        if timeEvent.get("type") in ("OPEN", "CLOSE"):
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
    
    def IsExchangeOpen(self, exchange: str, time: datetime) -> bool:
        if exchange not in self.exchangeTimes:
            return False
        
        todaysSchedules = [schedule for schedule in self.exchangeTimes[exchange] if schedule.get("date").date() == time.date()]

        isOpen = False
        for schedule in todaysSchedules:
            if schedule.get("type") == "OPEN" and schedule.get("date") <= time:
                isOpen = True
            elif schedule.get("type") == "CLOSE" and schedule.get("date") <= time:
                isOpen = False

        return isOpen

tickerList = ["AAPL_US_EQ"]

multiTrader = MultiStockTraderHandler(stockTickers=tickerList)