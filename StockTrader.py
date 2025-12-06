import pandas as pd
import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
import os
import Strategy
import time
import Trading212Api as api
import dotenv

# Load environment variables from .env file
env = dotenv.dotenv_values(".env")

class StockTrader:
    def __init__(self, ticker, balance, strategy, dynamicRisk: bool = True, benchmarkGraphs: bool = False, takeProfitPercent: float = 0.5, stopLossPercent: float = 0.05):
        self.benchmarkGraphs = benchmarkGraphs
        self.balance = balance
        self.ticker = ticker
        self.strategy = self.GetStrategy(strategy)
        self.dynamicRisk = dynamicRisk
        self.stopLossPercent = 0.05
        self.takeProfitPercent = 0.5
        self.data = self.GetStockData(interval="1h", period="1y")
        self.activeTrades = {}  # Dict with order_id as key for live trading
        self.pendingTrades = {}  # Dict with order_id as key for pending orders
        self.updateTimeFrameInSeconds = 10  # 1 day updates

        self.broker = api.Trading212Broker(api_key=os.getenv("API_KEY"), api_secret=os.getenv("API_SECRET"), paper_trading=True)

        if self.broker.authTestResult == False:
            print("Cannot Start Live Trading: Authentication Test Failed.")
            return
        
        self.TradingUpdateLoop()

    def TradingUpdateLoop(self):
        """Live trading loop - checks for signals and executes trades in real-time"""
        nextTradeId = 0
        timePassedInSeconds = 0
        
        while True:
            #Check For New Data
            self.data = self.GetStockData(interval="1h", period="1y")
            
            #Check current pending trades for fills
            orders_to_remove = []
            for order_id, pending_order in list(self.pendingTrades.items()):
                order_info = self.broker.CheckOrderStatus(order_id)

                if order_info.get("filled"):
                    # Move from pending to active (only for BUY orders - sells close positions)
                    if pending_order["type"] == "BUY":
                        self.activeTrades[order_id] = { 
                            "shares": pending_order["shares"],
                            "price": pending_order["price"],
                            "order_type": "BUY"
                        }
                    orders_to_remove.append(order_id)
                elif order_info.get("status") == "CANCELLED":
                    print(f"Order #{order_id} was cancelled.")
                    orders_to_remove.append(order_id)
                else:
                    print(f"Order #{order_id} Still Pending.")
                        
            
            # Remove filled orders from pending
            for order_id in orders_to_remove:
                del self.pendingTrades[order_id]

            #Check If We Should Buy Or Sell
            signals = self.strategy.GetSignals(self.data)
            
            # Get the most recent signal (last bar)
            latest_signal = signals.iloc[-1]['Signal']
            latest_price = signals.iloc[-1]['Close']
            latest_datetime = signals.iloc[-1]['Datetime']
            
            # Calculate total shares owned
            totalSharesOwned = sum(t["shares"] for t in self.activeTrades.values())
            
            # Check stop loss and take profit on existing positions
            orders_to_remove = []
            for order_id, trade in self.activeTrades.items():
                # Check if stop loss hit
                if latest_price <= trade["buy_price"] * (1 - self.stopLossPercent):
                    print(f"Stop Loss triggered for trade #{order_id} at ${latest_price:.2f}")
                    shares_to_sell = trade["shares"]
                    if self._execute_live_order("SELL", f"{self.ticker}_US_EQ", shares_to_sell, latest_price):
                        self.balance = round(self.balance + (shares_to_sell * latest_price), 2)
                        print(f"Sold {shares_to_sell} shares. New balance: ${self.balance:.2f}")
                        orders_to_remove.append(order_id)
                
                # Check if take profit hit
                elif latest_price >= trade["buy_price"] * (1 + self.takeProfitPercent):
                    print(f"Take Profit triggered for trade #{order_id} at ${latest_price:.2f}")
                    shares_to_sell = trade["shares"]
                    if self._execute_live_order("SELL", f"{self.ticker}_US_EQ", shares_to_sell, latest_price):
                        self.balance = round(self.balance + (shares_to_sell * latest_price), 2)
                        print(f"Sold {shares_to_sell} shares. New balance: ${self.balance:.2f}")
                        orders_to_remove.append(order_id)
            
            # Remove closed positions
            for order_id in orders_to_remove:
                del self.activeTrades[order_id]
            
            # Execute buy signal
            if latest_signal == 1:
                print(f"Buy Signal Detected at {latest_datetime}")
                self.activeTrades, self.balance, nextTradeId, executed = self.ExecuteBuy(
                    self.activeTrades, self.balance, latest_price, self.strategy, 
                    len(signals) - 1, nextTradeId, live_mode=True
                )
                if executed:
                    print(f"Buy executed. Balance: ${self.balance:.2f}, Active trades: {len(self.activeTrades)}")
            
            # Execute sell signal
            elif latest_signal == -1:
                print(f"Sell Signal Detected at {latest_datetime}")
                self.activeTrades, self.balance = self.ExecuteSell(
                    self.activeTrades, self.balance, latest_price, self.strategy,
                    len(signals) - 1, live_mode=True
                )
                print(f"Sell executed. Balance: ${self.balance:.2f}, Active trades: {len(self.activeTrades)}")
            
            # Print status
            total_invested = sum(t["shares"] * latest_price for t in self.activeTrades.values())
            pending_total = sum(t["shares"] * t["price"] for t in self.pendingTrades.values())
            total_value = self.balance + total_invested
            print(f"\nStatus: Cash=${self.balance:.2f}, Invested=${total_invested:.2f}, Total=${total_value:.2f}, Positions={len(self.activeTrades)}\nPending Orders={len(self.pendingTrades)} Pending Positisons=${pending_total:.2f}")
            print(f"Active Trades Detail: {self.activeTrades}")
            print(f"Pending Trades Detail: {self.pendingTrades}")

            time.sleep(self.updateTimeFrameInSeconds)  # Wait for 15 minutes before next check
            timePassedInSeconds += self.updateTimeFrameInSeconds

            # Periodically update strategy (e.g., every 24 hours)
            if timePassedInSeconds >= 3600:  # 24 hours
                print("\n--- Updating Strategy ---")
                self.UpdateStrategy()
                timePassedInSeconds = 0

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
        
    def GetStockData(self, interval: str, period: str):
        data = yf.download(self.ticker, interval=interval, period=period, auto_adjust=True)

        # Flatten MultiIndex columns if present (yfinance can return MultiIndex)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = ['_'.join(filter(None, col)).strip() for col in data.columns.values]

        # Normalize column names (e.g. 'Close_Adj' -> 'Close')
        renameMap = {column: column.split('_')[0] for column in data.columns}
        data = data.rename(columns=renameMap)

        # Ensure there's always a `Datetime` column.
        # Many data sources return a DatetimeIndex rather than a column; reset the index when needed.
        if 'Datetime' not in data.columns:
            data = data.reset_index()
            # If reset_index didn't produce a 'Datetime' column name (index had no name), rename the first column
            if 'Datetime' not in data.columns and len(data.columns) > 0:
                first_col = data.columns[0]
                data = data.rename(columns={first_col: 'Datetime'})

        data['Datetime'] = pd.to_datetime(data['Datetime'])

        data = data.sort_values(by='Datetime')

        return data

    def UpdateStrategy(self):
        print(f"Updating Strategy From {self.strategy.name}...\nRunning Benchmarks...")

        currentBestStrategy = self.strategy
        currentBestRoi = 0
        currentlyBenchmarking = self.strategy

        # Get Latest Data For Benchmarking
        self.data = self.GetStockData(interval="1h", period="1y")

        #Backtest All Strategies
        for strategy in Strategy.strategies.keys():
            currentlyBenchmarking = self.GetStrategy(strategy)

            signals = currentlyBenchmarking.GetSignals(self.data)
            
            # Debug: Count signals
            buy_signals = (signals['Signal'] == 1).sum()
            sell_signals = (signals['Signal'] == -1).sum()
            print(f"\n{currentlyBenchmarking.name}: {buy_signals} buy signals, {sell_signals} sell signals")

            # Data For Current Benchmark
            cash = self.balance
            activeTrades = []  # List of individual trades (each with unique ID, shares, buy_price)
            nextTradeId = 0
            tradeHistory = []
            trades_executed = 0

            # Run
            for i in range(len(signals)):
                signal = signals.iloc[i]['Signal']
                price = signals.iloc[i]['Close']

                # Calculate total shares owned across all active trades
                totalSharesOwned = sum(t["shares"] for t in activeTrades)

                # Check For Stop Loss and Take Profit Triggers on each active trade
                remainingTrades = []
                for trade in activeTrades:
                    #Check If Stop Loss Hit
                    if price <= trade["buy_price"] * (1 - self.stopLossPercent):
                        #Get Shares To Sell
                        sharesToSell = trade["shares"]
                        cash = round(cash + (sharesToSell * price), 2)
                        #Check If Graphic Benchmarking Enabled
                        if self.benchmarkGraphs:
                            self.AppendTradeHistory(tradeHistory, "stop_loss", price, signals.iloc[i]['Datetime'], sharesToSell)
                        # Trade closed, don't add to remainingTrades

                    #Check If Take Profit Hit
                    elif price >= trade["buy_price"] * (1 + self.takeProfitPercent):
                        sharesToSell = trade["shares"]
                        cash = round(cash + (sharesToSell * price), 2)
                        #Check If Graphic Benchmarking Enabled
                        if self.benchmarkGraphs:
                            self.AppendTradeHistory(tradeHistory, "take_profit", price, signals.iloc[i]['Datetime'], sharesToSell)
                        # Trade closed, don't add to remainingTrades
                    else:
                        # Trade still active
                        remainingTrades.append(trade)
                
                activeTrades = remainingTrades


                #Buy Signal - allow multiple concurrent positions
                if signal == 1:
                    activeTrades, cash, nextTradeId, executed = self.ExecuteBuy(
                        activeTrades, cash, price, currentlyBenchmarking, i, nextTradeId,
                        tradeHistory, signals.iloc[i]['Datetime'], trades_executed
                    )
                    if executed:
                        trades_executed += 1
                
                #Sell Signal - sell from oldest/worst performing trades
                elif signal == -1:
                    activeTrades, cash = self.ExecuteSell(
                        activeTrades, cash, price, currentlyBenchmarking, i,
                        tradeHistory, signals.iloc[i]['Datetime']
                    )

            #Benchmark Results
            finalShares = sum(t["shares"] for t in activeTrades)
            totalValue = cash + (finalShares * price)
            roi = (totalValue - self.balance) / self.balance
            
            print(f"  Trades executed: {trades_executed}, Final value: ${totalValue:.2f}, ROI: {roi*100:.2f}%")

            if self.benchmarkGraphs:
                self.GraphTradeHistory(tradeHistory, strategyName=currentlyBenchmarking.name)
            else:
                print(f"Strategy {currentlyBenchmarking.name} resulted in ROI: {roi*100:.2f}%")

            #Purge Trade History
            tradeHistory = self.activeTrades

            #Check If Best Strategy
            if roi > currentBestRoi:
                currentBestRoi = roi
                currentBestStrategy = currentlyBenchmarking

        #Set Best Strategy
        self.strategy = currentBestStrategy

        if self.strategy.name != currentlyBenchmarking.name:
            print(f"New Best Strategy Found: {self.strategy.name} with ROI: {currentBestRoi*100:.2f}%")
        else:
            print(f"No Better Strategy Found. Continuing With: {self.strategy.name} with ROI: {currentBestRoi*100:.2f}%")

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

    def _execute_live_order(self, order_type, ticker, shares, price):
        if order_type == "BUY":
            result = self.broker.PlaceOrder(ticker=ticker, limitPrice=price + 2, amount=shares)

            #Check If Order Was Successful
            if(result.get("success")):
                print(f"Buy Order Placed Filled Result: {result.get('filled')}\nOrder Id: {result.get('order_id')}")

                if(not result.get("filled")):
                    order_id = result.get("order_id")
                    self.pendingTrades[order_id] = {
                        "type": "BUY",
                        "ticker": ticker,
                        "shares": shares,
                        "price": price + 2
                    }
                else:
                    order_id = result.get("order_id")
                    self.activeTrades[order_id] = {
                        "shares": shares,
                        "ticker": ticker,
                        "price": price + 2,
                        "order_type": "BUY"
                    }
            else:
                print("Buy Order Failed to Place.")
                return False
        else:
            result = self.broker.PlaceSellOrder(ticker=ticker, limitPrice=price - 2, amount=shares)
            #Check If Order Was Successful
            if(result.get("success")):
                print(f"Sell Order Placed Filled Result: {result.get('filled')}\nOrder Id: {result.get('order_id')}")

                if(not result.get("filled")):
                    order_id = result.get("order_id")
                    self.pendingTrades[order_id] = {
                        "type": "SELL",
                        "ticker": ticker,
                        "shares": shares,
                        "price": price - 2
                    }
                else:
                    order_id = result.get("order_id")
                    self.pendingTrades[order_id] = {
                        "shares": shares,
                        "ticker": ticker,
                        "price": price - 2,
                        "order_type": "SELL"
                    }
            else:
                print("Sell Order Failed to Place.")
                return False

        return True  # Return success status

    def ExecuteBuy(self, activeTrades, cash, price, strategy, data_idx, nextTradeId, 
                   tradeHistory=None, datetime=None, debug_count=0, live_mode=False):
        """Execute buy signal and return updated (activeTrades, cash, nextTradeId, executed_flag)
        
        Args:
            live_mode: If True, executes real broker orders via _execute_live_order
        """
        # Validate we have positive cash to begin with
        if cash <= 0:
            return activeTrades, cash, nextTradeId, False
        
        # Handle both list (benchmark) and dict (live) structures
        if isinstance(activeTrades, dict):
            totalSharesOwned = sum(t["shares"] for t in activeTrades.values())
        else:
            totalSharesOwned = sum(t["shares"] for t in activeTrades)
        risk_factor, sharesToBuy = strategy.calculate_risk(
            self.data, data_idx, current_capital=cash, current_shares=totalSharesOwned, mode="buy"
        )
        
        # Calculate actual cost
        cost = sharesToBuy * price
        
        # CRITICAL: Ensure we never spend more than available cash
        if sharesToBuy > 0 and cost <= cash:
            # Double-check cost doesn't exceed cash (safety for rounding errors)
            if cost > cash:
                # Recalculate shares to exactly fit available cash
                sharesToBuy = round(cash / price, 2)
                cost = sharesToBuy * price
                # If still over (due to rounding), reduce by 0.01 shares
                if cost > cash:
                    sharesToBuy = max(0.0, sharesToBuy - 0.01)
                    cost = sharesToBuy * price
            
            # Final validation: only proceed if we have valid shares and can afford it
            if sharesToBuy > 0 and cost <= cash:
                # Execute live order if in live mode
                if live_mode:
                    success = self._execute_live_order("BUY", f"{self.ticker}_US_EQ", sharesToBuy, price)
                    if not success:
                        return activeTrades, cash, nextTradeId, False
                
                # Deduct cost and verify cash doesn't go negative
                new_cash = round(cash - cost, 2)
                if new_cash < 0:
                    print(f"WARNING: Buy would make cash negative! cash={cash}, cost={cost}. Skipping trade.")
                    return activeTrades, cash, nextTradeId, False
                
                cash = new_cash
                
                # Create new trade with unique ID
                # In live_mode, _execute_live_order already added to dict, just track the ID was used
                if not live_mode:
                    activeTrades.append({
                        "id": nextTradeId,
                        "shares": sharesToBuy,
                        "buy_price": price
                    })
                nextTradeId += 1
                
                # Optionally record to trade history
                if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                    self.AppendTradeHistory(tradeHistory, "buy", price, datetime, sharesToBuy)
                
                return activeTrades, cash, nextTradeId, True
        
        return activeTrades, cash, nextTradeId, False

    def ExecuteSell(self, activeTrades, cash, price, strategy, data_idx, 
                    tradeHistory=None, datetime=None, live_mode=False):
        """Execute sell signal and return updated (activeTrades, cash)
        
        Args:
            live_mode: If True, executes real broker orders via _execute_live_order
        """
        if len(activeTrades) == 0:
            return activeTrades, cash
        
        # Handle both list (benchmark) and dict (live) structures
        if isinstance(activeTrades, dict):
            totalSharesOwned = sum(t["shares"] for t in activeTrades.values())
            trades_list = list(activeTrades.items())  # [(order_id, trade), ...]
        else:
            totalSharesOwned = sum(t["shares"] for t in activeTrades)
            trades_list = [(t["id"], t) for t in activeTrades]  # Convert to same format

        risk_factor, sharesToSell = strategy.calculate_risk(
            self.data, data_idx, current_capital=cash, current_shares=totalSharesOwned, mode="sell"
        )
        
        if sharesToSell > 0:
            # Sort trades by performance (worst first) to close losing positions
            sorted_trades = sorted(trades_list, key=lambda item: (price - item[1]["buy_price"]) / item[1]["buy_price"])
            
            remaining_to_sell = sharesToSell
            
            if isinstance(activeTrades, dict):
                new_active = {}
                for order_id, trade in activeTrades.items():
                    new_active[order_id] = trade
            else:
                new_active = []
            
            for order_id, trade in sorted_trades:
                if remaining_to_sell <= 0:
                    if isinstance(activeTrades, list):
                        new_active.append(trade)
                    continue
                
                if trade["shares"] <= remaining_to_sell:
                    # Close entire trade
                    shares_to_close = trade["shares"]
                    
                    # Execute live order if in live mode
                    if live_mode:
                        success = self._execute_live_order("SELL", self.ticker, shares_to_close, price)
                        if not success:
                            if isinstance(activeTrades, list):
                                new_active.append(trade)
                            continue
                    
                    # Remove from dict or don't add to list
                    if isinstance(activeTrades, dict):
                        del new_active[order_id]
                    # For list, just don't append (already not in new_active)
                    
                    cash = round(cash + (shares_to_close * price), 2)
                    remaining_to_sell -= shares_to_close
                    if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                        self.AppendTradeHistory(tradeHistory, "sell", price, datetime, shares_to_close)
                else:
                    # Partial close
                    shares_to_close = remaining_to_sell
                    
                    # Execute live order if in live mode
                    if live_mode:
                        success = self._execute_live_order("SELL", self.ticker, shares_to_close, price)
                        if not success:
                            if isinstance(activeTrades, list):
                                new_active.append(trade)
                            continue
                    
                    cash = round(cash + (shares_to_close * price), 2)
                    
                    # Update shares in place
                    if isinstance(activeTrades, dict):
                        new_active[order_id]["shares"] = round(trade["shares"] - shares_to_close, 2)
                    else:
                        trade["shares"] = round(trade["shares"] - shares_to_close, 2)
                        new_active.append(trade)
                    
                    remaining_to_sell = 0
                    if tradeHistory is not None and datetime is not None and self.benchmarkGraphs:
                        self.AppendTradeHistory(tradeHistory, "sell", price, datetime, shares_to_close)
            
            activeTrades = new_active
        
        return activeTrades, cash

    def GraphTradeHistory(self, tradeHistory, strategyName = "NULL"):
        if not tradeHistory or len(tradeHistory) == 0:
            print("No trade history to plot.")
            return

        # Use datetime for x-axis (it always exists in self.data)
        df = self.data.copy()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df = df.set_index('Datetime')
        n = len(df)
        times = df.index
        price_arr = df['Close'].values

        # Map trades by datetime
        trade_map = {}
        for t in tradeHistory:
            dt = t.get('datetime')
            if dt is None:
                continue
            dt = pd.to_datetime(dt)
            # Find nearest time in index
            idx_array = times.get_indexer([dt], method='nearest')
            if len(idx_array) == 0:
                continue
            idx = idx_array[0]
            if idx == -1:
                continue
            trade_map.setdefault(idx, []).append(t)

        # Reconstruct portfolio over time from trades
        starting_balance = getattr(self, 'balance', 0)
        cash = starting_balance
        shares = 0
        cash_hist = []
        invested_hist = []
        total_hist = []

        # iterate over price bars
        for i, (ts, row) in enumerate(df.iterrows()):
            trades_here = trade_map.get(i, [])
            for tr in trades_here:
                typ = (tr.get('type') or '').lower()
                price = tr.get('price')
                t_shares = tr.get('shares', None)
                
                if typ == 'buy':
                    if t_shares is None or t_shares <= 0:
                        t_shares = 1  # Fallback for old trade history
                    cost = price * t_shares
                    # Prevent negative cash
                    if cost > cash:
                        print(f"WARNING: Buy at {ts} would overdraw cash. Adjusting.")
                        t_shares = cash / price if price > 0 else 0
                        cost = t_shares * price
                    cash -= cost
                    shares += t_shares
                elif typ == 'sell':
                    if t_shares is None:
                        t_shares = shares  # Sell all if not specified
                    t_shares = min(t_shares, shares)  # Can't sell more than owned
                    cash += price * t_shares
                    shares = max(0, shares - t_shares)
                elif typ in ('stop_loss', 'stop'):
                    if t_shares is None:
                        t_shares = shares  # Use all shares if not specified
                    t_shares = min(t_shares, shares)  # Can't sell more than owned
                    if t_shares > 0:
                        cash += price * t_shares
                        shares = max(0, shares - t_shares)
                elif typ in ('take_profit', 'tp'):
                    if t_shares is None:
                        t_shares = shares  # Use all shares if not specified
                    t_shares = min(t_shares, shares)  # Can't sell more than owned
                    if t_shares > 0:
                        cash += price * t_shares
                        shares = max(0, shares - t_shares)
            
            # Ensure cash never goes negative (failsafe)
            cash = max(0, cash)

            position_value = shares * row['Close']
            invested_hist.append(position_value)
            cash_hist.append(cash)
            total_hist.append(cash + position_value)

        # Create plots: top = price + markers, bottom = portfolio stacked
        fig, (ax_price, ax_port) = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                            gridspec_kw={'height_ratios': [2, 1]})

        # Price plot (x axis is datetime)
        ax_price.plot(times, price_arr, color='#073B4C', linewidth=1.5, label='Close')

        # Prepare marker lists from trade_map
        buys_x, buys_y = [], []
        sells_x, sells_y = [], []
        stops_x, stops_y = [], []
        tps_x, tps_y = [], []
        for idx, trades in trade_map.items():
            trade_time = times[idx]
            for tr in trades:
                typ = (tr.get('type') or '').lower()
                # Use the actual trade price recorded in the trade
                plot_price = tr.get('price', price_arr[idx])
                if typ == 'buy':
                    buys_x.append(trade_time); buys_y.append(plot_price)
                elif typ == 'sell':
                    sells_x.append(trade_time); sells_y.append(plot_price)
                elif typ in ('stop_loss', 'stop'):
                    stops_x.append(trade_time); stops_y.append(plot_price)
                elif typ in ('take_profit', 'tp'):
                    tps_x.append(trade_time); tps_y.append(plot_price)

        if buys_x:
            ax_price.scatter(buys_x, buys_y, marker='^', color='#06D6A0', edgecolors='black', s=60, label='Buy', zorder=6)
        if sells_x:
            ax_price.scatter(sells_x, sells_y, marker='v', color='#EF476F', edgecolors='black', s=60, label='Sell', zorder=6)
        if stops_x:
            ax_price.scatter(stops_x, stops_y, marker='x', color='black', s=50, label='Stop Loss', zorder=6)
        if tps_x:
            ax_price.scatter(tps_x, tps_y, marker='o', color='#118AB2', s=50, label='Take Profit', zorder=6)

        ax_price.set_ylabel('Price')
        ax_price.set_title(f'{self.ticker} Price and Trades')
        ax_price.legend(loc='best')
        ax_price.grid(alpha=0.3)

        # Portfolio plot: stacked area of cash and invested
        cash_arr = pd.Series(cash_hist, index=times)
        invested_arr = pd.Series(invested_hist, index=times)
        total_arr = pd.Series(total_hist, index=times)

        ax_port.plot(times, total_arr, color='#073B4C', linewidth=2, label='Total Portfolio')
        ax_port.fill_between(times, 0, cash_arr, color='#90C2E7', alpha=0.6, label='Cash')
        ax_port.fill_between(times, cash_arr, cash_arr + invested_arr, color='#06D6A0', alpha=0.6, label='Invested')

        ax_port.set_ylabel('Portfolio Value')
        ax_port.set_xlabel('Datetime')
        ax_port.legend(loc='best')
        ax_port.grid(alpha=0.3)

        plt.tight_layout()
        try:
            # Ensure output directory exists (use ticker as folder)
            out_dir = f"Trading_Graphs/{self.ticker}"
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            filename = f"{out_dir}/Trade_History_{strategyName}.png"
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"Saved trade history to {filename}")
        except Exception as e:
            print(f"Warning: failed to save trade history: {e}")

trader = StockTrader(ticker="AAPL", balance=150, strategy="MAC", benchmarkGraphs=True, dynamicRisk=True, takeProfitPercent=0.3, stopLossPercent=0.1)
