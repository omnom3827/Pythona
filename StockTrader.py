import json
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import os
import math
import Strategy
import APIs.Trading_APIs.Trading212Api as api
import APIs.Stock_Data_APIs.YahooApi as Yahoo
from Tools.StockOptimiser import StockOptimiser
from datetime import datetime, timezone

#Module
from APIs.BackTestBroker import BackTestBroker as BackTester

def floor_to_2dp(value):
    """Round down to 2 decimal places (conservative rounding)"""
    return math.floor(value * 100) / 100

class StockTrader:
    def __init__(self, ticker: str, balance: float, stockMultiHandler, dynamicRisk: bool = True, benchmarkGraphs: bool = False, takeProfitPercent: float = 0.25, stopLossPercent: float = 0.05, trailingStopPercent: float = 0.15,
                 marketToTradeIn: str = "NYSE", broker: api.Trading212Broker = None, stockDataInterval: str = "1h", stockDataPeriod: str = "1y", stocksApi: Yahoo.Yahoo = None, weekendsToWaitBeforeReconfig: int = 1):
        if(broker is None or stockMultiHandler is None or stocksApi is None):
            print(f"Cannot Start Instance For Ticker: {ticker}: Missing Required Components.")
            return
        
        
        self.tradingHistoryLocation = f"./TradingHistory/{ticker}_trading_history.json"
        self.stockApi = stocksApi
        self.benchmarkGraphs = benchmarkGraphs
        self.marketToTradeIn = marketToTradeIn
        self.balance = balance
        self.ticker = ticker
        self.strategy = None
        self.dynamicRisk = dynamicRisk
        self.stopLossPercent = stopLossPercent
        self.takeProfitPercent = takeProfitPercent
        self.trailingStopPercent = trailingStopPercent
        self.stockMultiHandler = stockMultiHandler
        self.stockDataInterval = stockDataInterval
        self.stockDataPeriod = stockDataPeriod
        self.becnhmarkRoi = 0.0
        self.activeTrades = {}  # Dict with order_id as key for live trading
        self.pendingTrades = {}  # Dict with order_id as key for pending orders
        self.UpdateStrategy()  # Default To Best Strategy
        self.data = self.stockApi.GetStockData(self.ticker.split("_")[0], interval=self.stockDataInterval, period=self.stockDataPeriod)
        self.signals = self.strategy.GetSignals(self.data)
        self.weekendsSinceLastReconfig = 0
        self.weekendsToWaitBeforeReconfig = weekendsToWaitBeforeReconfig

        self.ranMarketCloseMethods = False

        self.broker = broker


        #Load Previous Trading History If Exists
        self.LoadStateFromFile(self.tradingHistoryLocation)

    def TradingUpdateLoop(self):
        #Check current pending trades for fills
        orders_to_remove = []
        
        for order_id, pending_order in list(self.pendingTrades.items()):
            order_info = self.broker.CheckOrderStatus(order_id, newMethod=True, ticker=self.ticker)
            print(f"Checking Status For Pending Order #{order_id}")

            if order_info.get("filled"):
                # Move from pending to active (only for BUY orders - sells close positions)
                if pending_order["type"] == "BUY":
                    self.activeTrades[order_id] = { 
                        "shares": pending_order["shares"],
                        "price": pending_order["price"],
                        "order_type": "BUY"
                    }
                elif pending_order["type"] == "SELL":
                    # SELL filled - reduce/remove shares from active positions
                    shares_sold = pending_order["shares"]

                    if self.activeTrades.get(pending_order["affectedId"]) is not None:
                        # Update Share Count
                        if self.activeTrades[pending_order["affectedId"]]["shares"] - shares_sold <= 0:
                            del self.activeTrades[pending_order["affectedId"]]
                            print(f"Position #{pending_order['affectedId']} Fully Closed")
                        else:
                            self.activeTrades[pending_order["affectedId"]]["shares"] = floor_to_2dp(self.activeTrades[pending_order["affectedId"]]["shares"] - shares_sold)
                            print(f"Position #{pending_order['affectedId']} Reduced To {self.activeTrades[pending_order['affectedId']]['shares']} Shares")
                    else:
                        print(f"Warning: Affected Position #{pending_order['affectedId']} Not Found For Filled SELL Order #{order_id}.")
                
                orders_to_remove.append(order_id)
                print(f"Order #{order_id} Was Filled.")
            elif order_info.get("status") == "CANCELLED":
                print(f"Order #{order_id} Was Cancelled.")
                orders_to_remove.append(order_id)
            else:
                print(f"Order #{order_id} Still Pending.")

        # Remove filled/cancelled orders from pending
        for order_id in orders_to_remove:
            del self.pendingTrades[order_id]
        
        #Check if Exchange is Open
        if(self.stockMultiHandler.IsExchangeOpen(self.marketToTradeIn, datetime.now(timezone.utc)) == False):

            total_invested = sum(t["shares"] * self.signals.iloc[-1]['Close'] for t in self.activeTrades.values())
            pending_total = sum(t["shares"] * t["price"] for t in self.pendingTrades.values())
            total_value = self.balance + total_invested

            #Is It A Weekend
            if(self.weekendsSinceLastReconfig >= self.weekendsToWaitBeforeReconfig and datetime.now().weekday() >=5):
                self.OptimizeTradingParameters()
                self.weekendsSinceLastReconfig = 0
            #Update Trading Stratgey While Market Is Closed
            elif (self.ranMarketCloseMethods == False):
                print("Running Market Close Methods...")
                self.UpdateStrategy()
                self.ranMarketCloseMethods = True
                self.weekendsSinceLastReconfig += 1

            self.stockMultiHandler.traderRunHistory[self.ticker] = {
                "Cash": f"£{self.balance:.2f}",
                "Invested": f"£{total_invested:.2f}",
                "Total": f"£{total_value:.2f}",
                "Positions": len(self.activeTrades),
                "Pending Orders": len(self.pendingTrades),
                "Pending Positions Value": pending_total,
                "Current Trade Strategy": self.strategy.name,
                "Estimated ROI": f"{self.becnhmarkRoi*100:2f}%"
            }
            
            self.SaveStateToFile(self.tradingHistoryLocation)

            return
        elif (self.ranMarketCloseMethods):
            print("Market Opened. Resuming Trading.")
            self.ranMarketCloseMethods = False

        #Check For New Data
        self.data = self.stockApi.GetStockData(ticker=self.ticker.split("_")[0], interval=self.stockDataInterval, period=self.stockDataPeriod)
        self.signals = self.strategy.GetSignals(self.data)

        # Get the most recent signal (last bar)
        latest_signal = self.signals.iloc[-1]['Signal']
        latest_price = self.signals.iloc[-1]['Close']
        latest_datetime = self.signals.iloc[-1]['Datetime']
            
        # Check stop loss, trailing stop, and take profit on existing positions
        orders_to_remove = []
        for order_id, trade in self.activeTrades.items():
            # Track highest price seen for trailing stop
            if "highest_price" not in trade:
                trade["highest_price"] = trade["price"]
            
            # Update highest price
            if latest_price > trade["highest_price"]:
                trade["highest_price"] = latest_price
            
            # Check if stop loss hit
            if latest_price <= trade["price"] * (1 - self.stopLossPercent):
                print(f"Stop Loss triggered for trade #{order_id} at ${latest_price:.2f}")
                shares_to_sell = trade["shares"]
                if self.LiveOrder("SELL", self.ticker, shares_to_sell, latest_price, orderId=order_id):
                    print(f"Sold {shares_to_sell} shares. New balance: ${self.balance:.2f}")
                    orders_to_remove.append(order_id)
                
            # Check if trailing stop hit (only after profit threshold)
            elif latest_price >= trade["price"] * 1.05 and latest_price <= trade["highest_price"] * (1 - self.trailingStopPercent):
                print(f"Trailing Stop triggered for trade #{order_id} at ${latest_price:.2f} (highest was ${trade['highest_price']:.2f})")
                shares_to_sell = trade["shares"]
                if self.LiveOrder("SELL", self.ticker, shares_to_sell, latest_price, orderId=order_id):
                    print(f"Sold {shares_to_sell} shares. New balance: ${self.balance:.2f}")
                    orders_to_remove.append(order_id)
            
            # Check if take profit hit
            elif latest_price >= trade["price"] * (1 + self.takeProfitPercent):
                print(f"Take Profit triggered for trade #{order_id} at ${latest_price:.2f}")
                shares_to_sell = trade["shares"]
                if self.LiveOrder("SELL", self.ticker, shares_to_sell, latest_price, orderId=order_id):
                    print(f"Sold {shares_to_sell} shares. New balance: ${self.balance:.2f}")
                    orders_to_remove.append(order_id)
            
        # Remove closed positions
        for order_id in orders_to_remove:
            del self.activeTrades[order_id]
            
        # Execute buy signal
        if latest_signal == 1:
            print(f"Buy Signal Detected at {latest_datetime}")
            self.BuyApi(self.balance, latest_price)
        # Execute sell signal
        elif latest_signal == -1:
            print(f"Sell Signal Detected at {latest_datetime}")
            self.SellApi(self.balance, latest_price)
            
        # Print status
        total_invested = sum(t["shares"] * latest_price for t in self.activeTrades.values())
        pending_total = sum(t["shares"] * t["price"] for t in self.pendingTrades.values())
        total_value = self.balance + total_invested
        self.stockMultiHandler.traderRunHistory[self.ticker] = {
            "Cash": f"£{self.balance:.2f}",
            "Invested": f"£{total_invested:.2f}",
            "Total": f"£{total_value:.2f}",
            "Positions": len(self.activeTrades),
            "Pending Orders": len(self.pendingTrades),
            "Pending Positions Value": pending_total,
            "Current Trade Strategy": self.strategy.name,
            "Estimated ROI": f"{self.becnhmarkRoi*100:.2f}%"
        }

        # Save State
        self.SaveStateToFile(self.tradingHistoryLocation)

    def UpdateBalance(self, newBalance: float):
        self.balance = floor_to_2dp(newBalance)

    def GetStrategy(self, strategy: str):
        strategy_map = {
            "MAC": lambda: Strategy.MovingAverageCrossover(short_window=50, long_window=200),
            "RSI": lambda: Strategy.RSIStrategy(period=14, overbought=70, oversold=30),
            "Breakout": lambda: Strategy.BreakoutStrategy(window=20),
            "VolumeSpike": lambda: Strategy.VolumeSpikeStrategy(multiplier=2),
            "MACD": lambda: Strategy.MACDStrategy(fast=12, slow=26, signal=9),
            "BollingerBands": lambda: Strategy.BollingerBandsStrategy(window=20, num_std=2),
            "Momentum": lambda: Strategy.MomentumStrategy(lookback=14, threshold=0.02),
            "MeanReversion": lambda: Strategy.MeanReversionStrategy(window=20, std_threshold=1.5),
        }
        
        if strategy in strategy_map:
            return strategy_map[strategy]()
        else:
            raise ValueError(f"Unknown strategy: {strategy}. Available: {list(strategy_map.keys())}")

    def UpdateStrategy(self, newMethod: bool = True):

        if(newMethod):
            Backtest = BackTester(
                ticker=self.ticker.split("_")[0],
                startingBalance=self.balance,
                interval=self.stockDataInterval,
                period=self.stockDataPeriod,
                stopLossPercent=self.stopLossPercent,
                takeProfitPercent=self.takeProfitPercent,
                trailingStopPercent=self.trailingStopPercent,
                startingShares=self.activeTrades
            )

            strategy, roi = Backtest.RunBackTest()

            self.becnhmarkRoi = roi
            self.strategy = strategy
            return
        
        print("THIS METHOD HAS BEEN SUPERSEDED BY A NEW METHOD AND WILL BE REMOVED IN FUTURE VERSIONS."
        "PLEASE EXPECT ISSUES AND INCORRECT ROI RETURNS WHEN USING THIS METHOD.")

        if self.strategy is None:
            print("No Current Strategy Set. Initializing...")
        else:
            print(f"Updating Strategy From {self.strategy.name}...\nRunning Benchmarks...")

        currentBestStrategy = None
        currentBestRoi = -101
        currentlyBenchmarking = None

        # Get Latest Data For Benchmarking
        self.data = self.stockApi.GetStockData(ticker=self.ticker.split("_")[0], interval=self.stockDataInterval, period=self.stockDataPeriod)
        # benchmarkResults = pd.DataFrame(columns=["Strategy Name", "Total Value", "ROI"])
        benchmarkResults = {}

        #Backtest All Strategies
        for strategy in Strategy.strategies.keys():
            currentlyBenchmarking = self.GetStrategy(strategy)

            signals = currentlyBenchmarking.GetSignals(self.data)

            # Data For Current Benchmark
            cash = floor_to_2dp(self.balance)
            activeTrades = []  # List of individual trades (each with unique ID, shares, price)
            nextTradeId = 0
            tradeHistory = []
            trades_executed = 0

            # Run
            for i in range(len(signals)):
                signal = signals.iloc[i]['Signal']
                price = floor_to_2dp(signals.iloc[i]['Close'])

                # Check For Stop Loss, Trailing Stop, and Take Profit Triggers on each active trade
                remainingTrades = []
                for trade in activeTrades:
                    # Track highest price for trailing stop
                    if "highest_price" not in trade:
                        trade["highest_price"] = trade["price"]
                    
                    # Update highest price
                    if price > trade["highest_price"]:
                        trade["highest_price"] = price
                    
                    #Check If Stop Loss Hit
                    if price <= trade["price"] * (1 - self.stopLossPercent):
                        #Get Shares To Sell
                        sharesToSell = floor_to_2dp(trade["shares"])
                        cash = floor_to_2dp(cash + (sharesToSell * price))
                        #Check If Graphic Benchmarking Enabled
                        if self.benchmarkGraphs:
                            self.AppendTradeHistory(tradeHistory, "stop_loss", price, signals.iloc[i]['Datetime'], sharesToSell)

                    #Check If Trailing Stop Hit (only after 5% profit)
                    elif price >= trade["price"] * 1.05 and price <= trade["highest_price"] * (1 - self.trailingStopPercent):
                        sharesToSell = floor_to_2dp(trade["shares"])
                        cash = floor_to_2dp(cash + (sharesToSell * price))
                        if self.benchmarkGraphs:
                            self.AppendTradeHistory(tradeHistory, "trailing_stop", price, signals.iloc[i]['Datetime'], sharesToSell)

                    #Check If Take Profit Hit
                    elif price >= trade["price"] * (1 + self.takeProfitPercent):
                        sharesToSell = floor_to_2dp(trade["shares"])
                        cash = floor_to_2dp(cash + (sharesToSell * price))
                        #Check If Graphic Benchmarking Enabled
                        if self.benchmarkGraphs:
                            self.AppendTradeHistory(tradeHistory, "take_profit", price, signals.iloc[i]['Datetime'], sharesToSell)
                    else:
                        # Trade still active
                        remainingTrades.append(trade)
                
                activeTrades = remainingTrades


                #Buy Signal - allow multiple concurrent positions
                if signal == 1:
                    activeTrades, cash, nextTradeId, executed = self.ExecuteBuyBenchmark(
                        activeTrades, cash, price, currentlyBenchmarking, i, nextTradeId,
                        tradeHistory, signals.iloc[i]['Datetime'], trades_executed
                    )
                    if executed:
                        trades_executed += 1
                
                #Sell Signal - sell from oldest/worst performing trades
                elif signal == -1:
                    activeTrades, cash = self.ExecuteSellBenchmark(
                        activeTrades, cash, price, currentlyBenchmarking, i,
                        tradeHistory, signals.iloc[i]['Datetime']
                    )

            #Benchmark Results
            finalShares = floor_to_2dp(sum(t["shares"] for t in activeTrades))
            totalValue = floor_to_2dp(cash + (finalShares * price))
            roi = floor_to_2dp((totalValue - self.balance) / self.balance * 100) / 100

            if self.benchmarkGraphs:
                self.GraphTradeHistory(tradeHistory, strategyName=currentlyBenchmarking.name)

            benchmarkResults[currentlyBenchmarking.name] = {
                "End Value": totalValue,
                "ROI": roi,
                "Best": False
            }

            #Purge Trade History
            tradeHistory = self.activeTrades

            #Check If Best Strategy
            if roi > currentBestRoi:
                currentBestRoi = roi

                benchmarkResults[currentlyBenchmarking.name]["Best"] = True
                self.becnhmarkRoi = currentBestRoi

                if currentBestStrategy is not None:
                    benchmarkResults[currentBestStrategy.name]["Best"] = False

                currentBestStrategy = currentlyBenchmarking

        #Set Best Strategy
        self.strategy = currentBestStrategy

        print(f"Benchmark Results For {self.ticker}:")
        print(pd.DataFrame(benchmarkResults).T)

    def AppendTradeHistory(self, tradeHistory, type, price, datetime, shares=None):
        if self.benchmarkGraphs:
            tradeHistory.append({
                "type": type,
                "price": price,
                "datetime": datetime,
                "shares": shares  # Store actual shares bought/sold
            })
        else:
            print(f"{type} executed at {price} on {datetime}")

    def LiveOrder(self, order_type, ticker, shares, price, orderId: str = ""):
        if order_type == "BUY":
            result = self.broker.PlaceOrder(ticker=ticker, limitPrice=round(price, 2) + 2, amount=shares)

            #Check If Order Was Successful
            if(result.get("success")):
                print(f"Buy Order Placed Filled Result: {result.get('filled')}\nOrder Id: {result.get('order_id')}")

                if(not result.get("filled")):
                    order_id = result.get("order_id")
                    self.pendingTrades[order_id] = {
                        "type": "BUY",
                        "ticker": ticker,
                        "shares": floor_to_2dp(shares),
                        "price": floor_to_2dp(price + 2),
                    }
                    print(f"Buy Order Pending. Order Id: {order_id}")
                else:
                    order_id = result.get("order_id")
                    self.activeTrades[order_id] = {
                        "shares": floor_to_2dp(shares),
                        "ticker": ticker,
                        "price": floor_to_2dp(price + 2),
                    }
            else:
                print("Buy Order Failed To Place.")
                return False
        else:
            result = self.broker.PlaceSellOrder(ticker=ticker, limitPrice=round(price, 2) - 2, amount=shares)
            #Check If Order Was Successful
            if(result.get("success")):
                print(f"Sell Order Placed Filled Result: {result.get('filled')}\nOrder Id: {result.get('order_id')}")

                if(not result.get("filled")):
                    order_id = result.get("order_id")
                    self.pendingTrades[order_id] = {
                        "type": "SELL",
                        "ticker": ticker,
                        "shares": floor_to_2dp(shares),
                        "price": floor_to_2dp(price - 2),
                        "affectedId": orderId
                    }
                else:
                    #Check If All Shares Sold
                    if self.activeTrades.get(orderId)["shares"] - shares == 0:
                        del self.activeTrades[orderId]
                        self.balance = floor_to_2dp(self.balance + (shares * price))
                    else:
                        self.activeTrades[orderId]["shares"] = floor_to_2dp(self.activeTrades.get(orderId)["shares"] - shares)
                        self.balance = floor_to_2dp(self.balance + (shares * price))
            else:
                print("Sell Order Failed To Place.")
                return False

        return True  # Return success status

    def ExecuteBuyBenchmark(self, activeTrades, cash, price, strategy, data_idx, nextTradeId, tradeHistory=None, datetime=None, debug_count=0, live_mode=False):
        # Validate we have positive cash to begin with
        if cash <= 0:
            return activeTrades, cash, nextTradeId, False

        totalSharesOwned = sum(t["shares"] for t in activeTrades)

        risk_factor, sharesToBuy = strategy.calculate_risk(
            self.data, data_idx, current_capital=cash, current_shares=totalSharesOwned, mode="buy"
        )
        
        # Calculate actual cost
        cost = sharesToBuy * price
        
        # CRITICAL: Ensure we never spend more than available cash
        if sharesToBuy > 0 and cost <= cash:                          
            # Deduct cost and verify cash doesn't go negative
            new_cash = floor_to_2dp(cash - cost)

            if new_cash < 0:
                print(f"WARNING: Buy Would Make Cash Negative! Cash={cash}, Cost={cost}. Skipping Trade.")
                return activeTrades, cash, nextTradeId, False
                
            cash = new_cash
                
            # Create new trade with unique ID
            activeTrades.append({
                "id": nextTradeId,
                "shares": floor_to_2dp(sharesToBuy),
                "price": floor_to_2dp(price)
            })
                
            nextTradeId += 1
                
            # Optionally record to trade history
            if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                self.AppendTradeHistory(tradeHistory, "buy", price, datetime, sharesToBuy)
                
            return activeTrades, cash, nextTradeId, True
        
        return activeTrades, cash, nextTradeId, False
    
    def BuyApi(self, cash, price):
        if cash <= 0:
            print("No Cash Available To Buy Shares.")
            return
        
        # Work Out Cost
        risk_factor, sharesToBuy = self.strategy.calculate_risk(self.data, len(self.data)-1, current_capital=cash, current_shares=sum(t["shares"] for t in self.activeTrades.values()), mode="buy")

        sharesToBuy = floor_to_2dp(sharesToBuy)
        cost = floor_to_2dp(sharesToBuy * price)

        #Check we can afford this transaction
        if sharesToBuy > 0 and cost <= cash:
            if self.LiveOrder("BUY", self.ticker, sharesToBuy, price):
                self.balance = floor_to_2dp(self.balance - cost)
                print(f"Buy Order Executed. New Balance: ${self.balance:.2f}")

    
    def SellApi(self, cash, price):
        #Work Out Risk
        riskFactor, sharesToSell = self.strategy.calculate_risk(self.data, len(self.data)-1, current_capital=cash, current_shares=sum(t["shares"] for t in self.activeTrades.values()), mode="sell")

        sharesToSell = floor_to_2dp(sharesToSell)

        #Are We Selling More Then 0 Shares
        if sharesToSell > 0:
            #Close Losers First
            sortedTrades = sorted(self.activeTrades.items(), key=lambda item: (price - item[1]["price"]) / item[1]["price"])
            remaningToSell = sharesToSell

            for order_id, trade in sortedTrades:
                if remaningToSell <= 0:
                    break

                #Check If We Are Closing Entire Trade
                if trade["shares"] <= remaningToSell:
                    print(f"Running Full Close Sell For Trade Id: {order_id}")
                    sharesToSell = trade["shares"]

                    if self.LiveOrder("SELL", self.ticker, sharesToSell, price, orderId=order_id):
                        print(f"Sell Order Ran For Trade Id: {order_id}")
                        remaningToSell -= sharesToSell
                else:
                    print(f"Running Partial Close Sell For Trade Id: {order_id}")
                    sharesToSell = remaningToSell
                    
                    if self.LiveOrder("SELL", self.ticker, sharesToSell, price, orderId=order_id):
                        print(f"Sell Order Ran For Trade Id: {order_id}")
                        remaningToSell = 0
                        break  # Done selling

    def ExecuteSellBenchmark(self, activeTrades, cash, price, strategy, data_idx, tradeHistory=None, datetime=None, live_mode=False):
        if len(activeTrades) == 0:
            return activeTrades, cash
        
        totalSharesOwned = sum(t["shares"] for t in activeTrades)

        risk_factor, sharesToSell = strategy.calculate_risk(
            self.data, data_idx, current_capital=cash, current_shares=totalSharesOwned, mode="sell"
        )
        
        if sharesToSell > 0:
            # Sort trades by performance (worst first) to close losing positions
            sorted_trades = sorted(activeTrades, key=lambda item: (price - item["price"]) / item["price"])
            
            remaining_to_sell = sharesToSell
            
            new_active = []
            
            for trade in sorted_trades:
                if remaining_to_sell <= 0:
                    continue
                
                if trade["shares"] <= remaining_to_sell:
                    # Close entire trade
                    shares_to_close = floor_to_2dp(trade["shares"])

                    cash = floor_to_2dp(cash + (shares_to_close * price))
                    remaining_to_sell = floor_to_2dp(remaining_to_sell - shares_to_close)

                    if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                        self.AppendTradeHistory(tradeHistory, "sell", price, datetime, shares_to_close)
                else:
                    # Partial close
                    shares_to_close = floor_to_2dp(remaining_to_sell)
                    
                    cash = floor_to_2dp(cash + (shares_to_close * price))
                    
                    trade["shares"] = floor_to_2dp(trade["shares"] - shares_to_close)
                    new_active.append(trade)
                    
                    remaining_to_sell = 0.0
                    if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                        self.AppendTradeHistory(tradeHistory, "sell", price, datetime, shares_to_close)
            
            activeTrades = new_active
        
        return activeTrades, cash
    
    def OptimizeTradingParameters(self):
        print("Running Main Stock Optimisation. This Will Take A While")
        bestConfig = StockOptimiser(tickers=[self.ticker.split("_")[0]], initial_balance=self.balance, period="1y", interval="1h", stockDataApi=self.stockApi).RunOptimisation(loggingLevel=1, runtimeHistoryLimit=5)

        #Update Settings With New Best Config
        self.stopLossPercent = bestConfig[self.ticker.split("_")[0]]["params"]["stopLossPercent"]
        self.takeProfitPercent = bestConfig[self.ticker.split("_")[0]]["params"]["takeProfitPercent"]
        self.trailingStopPercent = bestConfig[self.ticker.split("_")[0]]["params"]["trailingStopPercent"]
        self.becnhmarkRoi = bestConfig[self.ticker.split("_")[0]]["roi"]
        self.strategy = bestConfig[self.ticker.split("_")[0]]["tradingMethod"]
        print(f"Updated Trading Parameters For {self.ticker}:\nStop Loss: {self.stopLossPercent}\nTake Profit: {self.takeProfitPercent}\nTrailing Stop: {self.trailingStopPercent}\nEstimated ROI: {self.becnhmarkRoi*100:.2f}%\nStrategy: {bestConfig[self.ticker.split('_')[0]]['tradingMethod'].name}")

    def SaveStateToFile(self, filepath: str):
        tradingStatus = {
            "ticker": self.ticker,
            # stringify keys so JSON can always serialize (handles numpy.int64)
            "activeTrades": {k: v for k, v in self.activeTrades.items()},
            "pendingTrades": {k: v for k, v in self.pendingTrades.items()},
            "config": {
                "stopLossPercent": self.stopLossPercent,
                "takeProfitPercent": self.takeProfitPercent,
                "trailingStopPercent": self.trailingStopPercent,
            }
        }

        dirLocation = filepath.rsplit('/', 1)[0]
        
        if not os.path.exists(filepath):
            print(f"Creating Directory For Trading State: {dirLocation}")
            # Make The Directory
            os.makedirs(dirLocation, exist_ok=True)

        try:
            with open(filepath, 'w') as f:
                json.dump(tradingStatus, f, indent=4)
            print(f"Successfully wrote trading state to {filepath}")
        except Exception as e:
            print(f"Warning: failed to write trading state to {filepath}: {e}")

    def LoadStateFromFile(self, filepath: str):
        if not os.path.exists(filepath):
            print(f"Previous State File Not Found: {filepath}. Building State From Broker Data.")
            self.BuildStateFromBroker()
            return
        
        try:
            with open(filepath, 'r') as f:
                tradingStatus = json.load(f)
            
            self.ticker = tradingStatus.get("ticker", self.ticker)
            activeTrades = tradingStatus.get("activeTrades", {})
            pendingTrades = tradingStatus.get("pendingTrades", {})

            self.activeTrades = { int(k): v for k, v in activeTrades.items() }
            self.pendingTrades = { int(k): v for k, v in pendingTrades.items() }

            print(f"Successfully loaded trading state from {filepath}")

            #Overried Config
            config = tradingStatus.get("config", {})

            if config != {}:
                print(f"Base Config Override From Loaded State.")
                self.stopLossPercent = config.get("stopLossPercent", self.stopLossPercent)
                self.takeProfitPercent = config.get("takeProfitPercent", self.takeProfitPercent)
                self.trailingStopPercent = config.get("trailingStopPercent", self.trailingStopPercent)
        except Exception as e:
            print(f"Warning: failed to load trading state from {filepath}: {e}\nSome Trades WILL BE LOST!!!!")
            self.BuildStateFromBroker()


    def BuildStateFromBroker(self):
        pendingOrders = self.broker.GetAllPendingOrders(self.ticker)
        openPosition = self.broker.GetOpenPositions(self.ticker)

        if openPosition is not None:
            self.activeTrades[openPosition.get("id")] = {
                "ticker": self.ticker,
                "shares": openPosition.get("shares"),
                "price": openPosition.get("price"),
            }

        for order in pendingOrders:
            if order.get("type") == "BUY":
                print("TODO: Rebuild Pending Buy Orders From Broker Data - Currently Not Supported.")
            else:
                print("TODO: Rebuild Pending Sell Orders From Broker Data - Currently Not Supported.")

        print("We Are Working To Add Support To Load From Trading212.")