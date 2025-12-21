import pandas as pd
import Strategy
from APIs.Stock_Data_APIs.YahooApi import Yahoo
import math

def floor_to_2dp(value):
    """Round down to 2 decimal places (conservative rounding)"""
    return math.floor(value * 100) / 100

class BackTestBroker:
    def __init__(self, ticker: str, startingBalance: float, period: str, interval: str, stopLossPercent: float, takeProfitPercent: float, 
                 trailingStopPercent: float, startingShares: dict = {}, backtestGraphs: bool = False, cashedData: pd.DataFrame = None):
        self.ticker = ticker
        self.startingBalance = startingBalance
        self.balance = startingBalance
        self.stockApi = Yahoo()
        self.stopLossPercent = stopLossPercent
        self.takeProfitPercent = takeProfitPercent
        self.trailingStopPercent = trailingStopPercent

        if cashedData is None:
            self.data = self.stockApi.GetStockData(self.ticker, period, interval)
        else:
            self.data = cashedData

        self.benchmarkGraphs = backtestGraphs
        self.baseTrades = {}

        #Convert Starting Shares
        negativeIndex = len(startingShares) * -1
        for trade in startingShares.values():
            self.baseTrades[negativeIndex] = {
                "shares": trade["shares"],
                "price": trade["price"],
                "highest_price": trade["price"]
            }
            negativeIndex += 1

    def RunBackTest(self, logResults: bool = True):
        bestTradeHistory = {}
        becnhmarkResults = {}
        currentBestStrategy = None
        currentBestRoi = -101

        #Loop Over Each Strategy
        for strategy in Strategy.strategies.keys():
            currentBenchmark = self.GetStrategy(strategy)
            signals = currentBenchmark.GetSignals(self.data)
            
            # Merge signals into data (left join to keep all data rows)
            merged_data = self.data.merge(signals[['Datetime', 'Signal']], on='Datetime', how='left')
            merged_data.rename(columns={"Signal_y": "Signal", "Close_x": "Close"}, inplace=True)
            merged_data.drop(columns=["Signal_x"], inplace=True)
            merged_data['Signal'] = merged_data['Signal'].fillna(0)  # Fill missing signals with 0
            
            self.balance = self.startingBalance
            activeTrades = self.baseTrades.copy()
            tradeHistory = {}
            
            # Loop over ALL data rows to check stop/take profit on every candle
            for i, row in merged_data.iterrows():
                current_price = row['Close']
                signal = row['Signal']

                #Check For Stop/Take Profit Triggers
                tradesToRemove = []
                for id in activeTrades.keys():
                    order = activeTrades[id]   
                    # Update highest price
                    if row["Close"] > order["highest_price"]:
                        order["highest_price"] = row["Close"]
                    
                    #Check If Stop Loss Hit
                    if row["Close"] <= order["price"] * (1 - self.stopLossPercent):
                        #Get Shares To Sell
                        sharesToSell = floor_to_2dp(order["shares"])
                        self.balance = floor_to_2dp(self.balance + (sharesToSell * current_price))
                        tradesToRemove.append(id)

                        if self.benchmarkGraphs:
                            tradeHistory[row['Datetime']] = { 
                                "action": "stop_loss",
                                "price": current_price,
                                "shares": sharesToSell
                            }

                    #Check If Trailing Stop Hit (only after 5% profit)
                    elif current_price >= order["price"] * 1.05 and current_price <= order["highest_price"] * (1 - self.trailingStopPercent):
                        sharesToSell = floor_to_2dp(order["shares"])
                        self.balance = floor_to_2dp(self.balance + (sharesToSell * current_price))
                        tradesToRemove.append(id)

                        if self.benchmarkGraphs:
                            tradeHistory[row['Datetime']] = { 
                                "action": "trailing_stop",
                                "price": current_price,
                                "shares": sharesToSell
                            }

                    #Check If Take Profit Hit
                    elif current_price >= order["price"] * (1 + self.takeProfitPercent):
                        sharesToSell = floor_to_2dp(order["shares"])
                        self.balance = floor_to_2dp(self.balance + (sharesToSell * current_price))
                        tradesToRemove.append(id)

                #Remove Closed Trades
                for trade in tradesToRemove:
                    del activeTrades[trade]

                #Check Signal
                if signal == 1: #Buy
                    self.BenchmarkBuy(price=current_price, sharesOwned=sum(trade['shares'] for trade in activeTrades.values()), index=i, strategy=currentBenchmark, activeTrades=activeTrades, tradeHistory=tradeHistory, datetime=row['Datetime'])
                elif signal == -1: #Sell
                    self.BenchmarkSell(price=current_price, sharesOwned=sum(trade['shares'] for trade in activeTrades.values()), index=i, strategy=currentBenchmark, activeTrades=activeTrades, tradeHistory=tradeHistory, datetime=row['Datetime'])

            #Calculate ROI (use final row price)
            final_price = merged_data.iloc[-1]['Close']
            totalValue = self.balance + sum(trade['shares'] * final_price for trade in activeTrades.values())
            roi = floor_to_2dp((totalValue - self.startingBalance) / self.startingBalance)

            if(roi > currentBestRoi):
                #Update Best Benchmark
                becnhmarkResults[currentBenchmark.name] = {
                    "End Value": totalValue,
                    "ROI": roi,
                    "Best": True
                }

                if currentBestStrategy is not None:
                    becnhmarkResults[currentBestStrategy.name]["Best"] = False

                currentBestRoi = roi
                currentBestStrategy = currentBenchmark
                bestTradeHistory = tradeHistory
            else:
                becnhmarkResults[currentBenchmark.name] = {
                    "End Value": totalValue,
                    "ROI": roi,
                    "Best": False
                }

        #Print Results
        if logResults:
            print(f"Backtest Results for {self.ticker}:")
            print(f"{pd.DataFrame(becnhmarkResults).T}")
        #Return Best Strategy And ROI
        return currentBestStrategy, currentBestRoi
                

    def BenchmarkBuy(self, price: float, index: int, sharesOwned: float, strategy, activeTrades: dict, tradeHistory: dict, datetime):
        #Check If Benchmark Has Cash
        if self.balance <= 0:
            return False
        
        #Check Risk
        risk_factor, sharesToBuy = strategy.calculate_risk(
            self.data, index, current_capital=self.balance, current_shares=sharesOwned, mode="buy"
        )

        #Get Total Cost
        totalCost = floor_to_2dp(sharesToBuy * price)

        #Check If Is Actually Buying Shares
        if(sharesToBuy > 0):
            self.balance = floor_to_2dp(self.balance - totalCost)

            # Mark Trade As Active
            activeTrades[index] = {
                "shares": sharesToBuy,
                "price": price,
                "highest_price": price
            }

            if self.benchmarkGraphs:
                tradeHistory[datetime] = { 
                    "action": "buy",
                    "price": price,
                    "shares": sharesToBuy
                }

    def BenchmarkSell(self, price: float, index: int, sharesOwned: float, strategy, activeTrades: dict, tradeHistory: dict, datetime):
        #Check If Has Shares To Sell
        if sharesOwned <= 0:
            return False
        
        #Check Risk
        risk_factor, sharesToSell = strategy.calculate_risk(
            self.data, index, current_capital=self.balance, current_shares=sharesOwned, mode="sell"
        )

        #Get Total Revenue
        totalRevenue = floor_to_2dp(sharesToSell * price)

        #Check If Is Actually Selling Shares
        if(sharesToSell > 0):
            self.balance = floor_to_2dp(self.balance + totalRevenue)

            # Remove Shares From Active Trades
            shares_to_sell = sharesToSell
            trades_to_remove = []
            for trade_index, trade in activeTrades.items():
                if trade['shares'] <= shares_to_sell:
                    shares_to_sell -= trade['shares']
                    trades_to_remove.append(trade_index)
                else:
                    trade['shares'] -= shares_to_sell
                    shares_to_sell = 0
                    break
            for trade_index in trades_to_remove:
                del activeTrades[trade_index]
        
            if self.benchmarkGraphs:
                tradeHistory[datetime] = { 
                    "action": "sell",
                    "price": price,
                    "shares": sharesToSell
                }

            

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
