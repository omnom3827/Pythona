import yfinance as yf
import pandas as pd
from abc import ABC, abstractmethod
import matplotlib.pyplot as plt

# -----------------------------
# Strategy Base Class
# -----------------------------
class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame):
        pass


# -----------------------------
# Strategy 1: Moving Average Crossover
# -----------------------------
class MovingAverageCrossover(Strategy):
    def __init__(self, short_window=20, long_window=50):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, data: pd.DataFrame):
        data['SMA_short'] = data['Close'].rolling(self.short_window).mean()
        data['SMA_long'] = data['Close'].rolling(self.long_window).mean()
        data['Signal'] = 0
        
        # Only signal on CROSSOVERS (not continuous holds)
        prev_short = data['SMA_short'].shift(1)
        prev_long = data['SMA_long'].shift(1)
        
        # Golden cross: short crosses ABOVE long = BUY
        data.loc[(prev_short <= prev_long) & (data['SMA_short'] > data['SMA_long']), 'Signal'] = 1
        
        # Death cross: short crosses BELOW long = SELL
        data.loc[(prev_short >= prev_long) & (data['SMA_short'] < data['SMA_long']), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 2: RSI Strategy
# -----------------------------
class RSIStrategy(Strategy):
    def __init__(self, period=14, overbought=70, oversold=30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def generate_signal(self, data: pd.DataFrame):
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        data['Signal'] = 0
        
        # Only signal when CROSSING thresholds (not staying in zones)
        prev_rsi = data['RSI'].shift(1)
        
        # RSI crosses BELOW oversold = BUY signal
        data.loc[(prev_rsi >= self.oversold) & (data['RSI'] < self.oversold), 'Signal'] = 1
        
        # RSI crosses ABOVE overbought = SELL signal
        data.loc[(prev_rsi <= self.overbought) & (data['RSI'] > self.overbought), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 3: Breakout Strategy
# -----------------------------
class BreakoutStrategy(Strategy):
    def __init__(self, window=20):
        self.window = window

    def generate_signal(self, data: pd.DataFrame):
        data['High_max'] = data['High'].rolling(self.window).max()
        data['Low_min'] = data['Low'].rolling(self.window).min()
        data['Signal'] = 0
        
        # Only signal on the FIRST breakout (not continuous holds above/below)
        prev_close = data['Close'].shift(1)
        prev_high_max = data['High_max'].shift(1)
        prev_low_min = data['Low_min'].shift(1)
        
        # Upside breakout: close crosses ABOVE previous high
        data.loc[(prev_close <= prev_high_max) & (data['Close'] > data['High_max']), 'Signal'] = 1
        
        # Downside breakdown: close crosses BELOW previous low
        data.loc[(prev_close >= prev_low_min) & (data['Close'] < data['Low_min']), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 4: Volume Spike Strategy
# -----------------------------
class VolumeSpikeStrategy(Strategy):
    def __init__(self, multiplier=2):
        self.multiplier = multiplier

    def generate_signal(self, data: pd.DataFrame):
        avg_vol = data['Volume'].rolling(20).mean()
        data['Signal'] = 0
        
        # Only signal when volume SPIKES (crosses above threshold), not continuous high volume
        prev_vol = data['Volume'].shift(1)
        prev_avg_vol = avg_vol.shift(1)
        threshold = prev_avg_vol * self.multiplier
        
        # Volume spike with price increase = BUY
        price_up = data['Close'] > data['Close'].shift(1)
        data.loc[(prev_vol <= threshold) & (data['Volume'] > avg_vol * self.multiplier) & price_up, 'Signal'] = 1
        
        # Volume spike with price decrease = SELL
        price_down = data['Close'] < data['Close'].shift(1)
        data.loc[(prev_vol <= threshold) & (data['Volume'] > avg_vol * self.multiplier) & price_down, 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 5: MACD Strategy
# -----------------------------
class MACDStrategy(Strategy):
    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signal(self, data: pd.DataFrame):
        # Calculate MACD
        exp1 = data['Close'].ewm(span=self.fast, adjust=False).mean()
        exp2 = data['Close'].ewm(span=self.slow, adjust=False).mean()
        data['MACD'] = exp1 - exp2
        data['Signal_Line'] = data['MACD'].ewm(span=self.signal, adjust=False).mean()
        data['Signal'] = 0
        
        # Only signal on crossovers
        prev_macd = data['MACD'].shift(1)
        prev_signal = data['Signal_Line'].shift(1)
        
        # MACD crosses above signal line = BUY
        data.loc[(prev_macd <= prev_signal) & (data['MACD'] > data['Signal_Line']), 'Signal'] = 1
        
        # MACD crosses below signal line = SELL
        data.loc[(prev_macd >= prev_signal) & (data['MACD'] < data['Signal_Line']), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 6: Bollinger Bands Strategy
# -----------------------------
class BollingerBandsStrategy(Strategy):
    def __init__(self, window=20, num_std=2):
        self.window = window
        self.num_std = num_std

    def generate_signal(self, data: pd.DataFrame):
        # Calculate Bollinger Bands
        data['SMA'] = data['Close'].rolling(self.window).mean()
        data['STD'] = data['Close'].rolling(self.window).std()
        data['Upper_Band'] = data['SMA'] + (data['STD'] * self.num_std)
        data['Lower_Band'] = data['SMA'] - (data['STD'] * self.num_std)
        data['Signal'] = 0
        
        # Only signal on band crossings
        prev_close = data['Close'].shift(1)
        
        # Price crosses BELOW lower band = BUY (oversold)
        data.loc[(prev_close >= data['Lower_Band'].shift(1)) & (data['Close'] < data['Lower_Band']), 'Signal'] = 1
        
        # Price crosses ABOVE upper band = SELL (overbought)
        data.loc[(prev_close <= data['Upper_Band'].shift(1)) & (data['Close'] > data['Upper_Band']), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 7: Momentum Strategy
# -----------------------------
class MomentumStrategy(Strategy):
    def __init__(self, lookback=14, threshold=0.02):
        self.lookback = lookback
        self.threshold = threshold  # 2% momentum threshold

    def generate_signal(self, data: pd.DataFrame):
        # Calculate momentum (rate of change)
        data['Momentum'] = data['Close'].pct_change(self.lookback)
        data['Signal'] = 0
        
        # Only signal when momentum crosses thresholds
        prev_momentum = data['Momentum'].shift(1)
        
        # Momentum crosses ABOVE positive threshold = BUY (strong upward momentum)
        data.loc[(prev_momentum <= self.threshold) & (data['Momentum'] > self.threshold), 'Signal'] = 1
        
        # Momentum crosses BELOW negative threshold = SELL (strong downward momentum)
        data.loc[(prev_momentum >= -self.threshold) & (data['Momentum'] < -self.threshold), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Strategy 8: Mean Reversion Strategy
# -----------------------------
class MeanReversionStrategy(Strategy):
    def __init__(self, window=20, std_threshold=1.5):
        self.window = window
        self.std_threshold = std_threshold

    def generate_signal(self, data: pd.DataFrame):
        # Calculate mean and standard deviation
        data['SMA'] = data['Close'].rolling(self.window).mean()
        data['STD'] = data['Close'].rolling(self.window).std()
        data['Z_Score'] = (data['Close'] - data['SMA']) / data['STD']
        data['Signal'] = 0
        
        # Only signal when crossing thresholds
        prev_z = data['Z_Score'].shift(1)
        
        # Z-score crosses BELOW -threshold = BUY (oversold, expect reversion up)
        data.loc[(prev_z >= -self.std_threshold) & (data['Z_Score'] < -self.std_threshold), 'Signal'] = 1
        
        # Z-score crosses ABOVE +threshold = SELL (overbought, expect reversion down)
        data.loc[(prev_z <= self.std_threshold) & (data['Z_Score'] > self.std_threshold), 'Signal'] = -1
        
        return data[['Datetime', 'Signal']]


# -----------------------------
# Trading Bot + Paper Trading Engine
# -----------------------------
# -----------------------------
class TradingBot:
    # Plot trades
    def plot_trades(self, data: pd.DataFrame, signals: pd.DataFrame, starting_balance: float, final_balance: float):
        """Plot comprehensive benchmark performance matching agent's 4-panel layout"""
        merged = data.copy()
        
        # Calculate metrics
        profit_loss = final_balance - starting_balance
        profit_percent = (profit_loss / starting_balance) * 100
        num_trades = len(self.executed_trades)
        
        # Create 4-panel figure matching agent layout
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
        
        # PANEL 1: Stock Price with Buy/Sell markers
        ax1.plot(range(len(merged)), merged['Close'], color='#073B4C', linewidth=2, label='Stock Price', zorder=1)
        
        # Plot executed trades
        if len(self.executed_trades) > 0:
            buy_steps, buy_prices = [], []
            sell_steps, sell_prices = [], []
            
            for trade in self.executed_trades:
                idx = trade['index']
                if idx < len(merged):
                    if trade['action'] == 'BUY':
                        buy_steps.append(idx)
                        buy_prices.append(trade['price'])
                    else:
                        sell_steps.append(idx)
                        sell_prices.append(trade['price'])
            
            if buy_steps:
                ax1.scatter(buy_steps, buy_prices, color='#06D6A0', marker='^', s=25, zorder=3, 
                          edgecolors='black', linewidths=0.5, alpha=0.7, label='Buy')
            if sell_steps:
                ax1.scatter(sell_steps, sell_prices, color='#EF476F', marker='v', s=25, zorder=3, 
                          edgecolors='black', linewidths=0.5, alpha=0.7, label='Sell')
        
        ax1.set_ylabel('Stock Price ($)', fontsize=10)
        ax1.set_title(f'Benchmark Strategy | Trades: {num_trades}', fontsize=12, fontweight='bold')
        ax1.legend(loc='best', fontsize=8)
        ax1.grid(True, alpha=0.3)
        
        # PANEL 2: Portfolio Value Over Time
        if len(self.portfolio_value_history) > 0:
            ax2.plot(range(len(self.portfolio_value_history)), self.portfolio_value_history, 
                    color='#118AB2', linewidth=2, label='Portfolio Value')
            ax2.axhline(y=starting_balance, color='gray', linestyle='--', linewidth=1, 
                       alpha=0.5, label='Initial Balance')
            
            profit_color = '#06D6A0' if profit_loss >= 0 else '#EF476F'
            profit_label = f'Final: ${final_balance:.2f} ({profit_percent:+.2f}%) | Reward: N/A'
            ax2.text(0.98, 0.02, profit_label, transform=ax2.transAxes, fontsize=9,
                    verticalalignment='bottom', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor=profit_color, alpha=0.2))
        
        ax2.set_ylabel('Portfolio Value ($)', fontsize=10)
        ax2.set_title('Portfolio Value Over Time', fontsize=10, fontweight='bold')
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.3)
        
        # PANEL 3: Portfolio Composition (Cash vs Position Value)
        if len(self.balance_history) > 0 and len(self.shares_history) > 0:
            # Calculate position values
            steps = range(len(self.balance_history))
            prices = merged['Close'].values[:len(steps)]
            position_values = [self.shares_history[i] * prices[i] for i in range(len(steps))]
            
            ax3.fill_between(steps, 0, self.balance_history, color='#90C2E7', alpha=0.6, label='Cash Balance')
            ax3.fill_between(steps, self.balance_history, 
                           [self.balance_history[i] + position_values[i] for i in range(len(steps))],
                           color='#06D6A0', alpha=0.6, label='Position Value')
            ax3.plot(steps, self.portfolio_value_history, color='#073B4C', linewidth=2, label='Total Portfolio')
        
        ax3.set_xlabel('Trading Steps', fontsize=10)
        ax3.set_ylabel('Value ($)', fontsize=10)
        ax3.set_title('Portfolio Composition', fontsize=10, fontweight='bold')
        ax3.legend(loc='upper left')
        ax3.grid(True, alpha=0.3)
        
        # PANEL 4: Position Size Over Time
        if len(self.shares_history) > 0:
            avg_shares = sum(self.shares_history) / len(self.shares_history)
            ax4.fill_between(range(len(self.shares_history)), 0, self.shares_history, 
                           color='#EF476F', alpha=0.5)
            ax4.plot(range(len(self.shares_history)), self.shares_history, 
                    color='#C1121F', linewidth=1.5, label='Shares Owned')
            ax4.axhline(y=avg_shares, color='gray', linestyle='--', linewidth=1, 
                       alpha=0.7, label=f'Avg: {avg_shares:.1f}')
        
        ax4.set_xlabel('Trading Steps', fontsize=10)
        ax4.set_ylabel('Number of Shares', fontsize=10)
        ax4.set_title('Position Size Over Time', fontsize=10, fontweight='bold')
        ax4.legend(loc='upper left')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('trading_signals.png', dpi=100, bbox_inches='tight')
        plt.close()

    
    def __init__(self, starting_balance=1000, risk_per_trade=0.30, take_profit_percent=0.30, stop_loss_percent=0.03, dynamic_risk=True):
        self.strategies = {
            'ma_crossover': MovingAverageCrossover(),
            'rsi': RSIStrategy(),
            'breakout': BreakoutStrategy(),
            'volume_spike': VolumeSpikeStrategy(),
            'macd': MACDStrategy(),
            'bollinger_bands': BollingerBandsStrategy(),
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
        }
        self.current_strategy = None
        # Paper trading state
        self.balance = starting_balance
        self.starting_balance = starting_balance
        self.position = 0
        self.position_price = 0
        self.activePositions = {}  # {ticker: {'shares': int, 'entry_price': float}}
        self.base_risk_per_trade = risk_per_trade  # Base risk level
        self.risk_per_trade = risk_per_trade  # Current risk level (will be adjusted dynamically)
        self.take_profit_percent = take_profit_percent
        self.stop_loss_percent = stop_loss_percent
        self.dynamic_risk = dynamic_risk
        # Track performance for dynamic risk
        self.trade_history = []  # List of profit/loss percentages from closed trades
        self.win_streak = 0
        self.loss_streak = 0
        self.executed_trades = []  # Track actual executed trades with timestamps for plotting
        
        # Track portfolio history for detailed plotting (like agent)
        self.balance_history = []
        self.shares_history = []
        self.portfolio_value_history = []

    def set_strategy(self, strategy_name: str):
        if strategy_name not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        self.current_strategy = self.strategies[strategy_name]

    def round_down(self, value: float, decimals: int = 2) -> float:
        """Round down to specified decimal places"""
        multiplier = 10 ** decimals
        return int(value * multiplier) / multiplier

    def calculate_dynamic_risk(self, data_slice: pd.DataFrame, current_index: int) -> float:
        """Calculate dynamic risk based on volatility and recent performance"""
        if not self.dynamic_risk:
            return self.base_risk_per_trade
        
        risk = self.base_risk_per_trade
        
        # Factor 1: Market volatility (last 20 periods)
        lookback = min(20, current_index)
        if lookback > 1:
            recent_prices = data_slice.iloc[max(0, current_index - lookback):current_index]['Close']
            volatility = recent_prices.pct_change().std()
            
            # Less conservative in volatility - volatile bull markets have opportunities
            if volatility > 0.05:  # Very high volatility only
                risk *= 0.7  # Less reduction
            elif volatility < 0.01:  # Low volatility
                risk *= 1.5
        
        # Factor 2: Recent trading performance
        if len(self.trade_history) >= 3:
            recent_trades = self.trade_history[-5:]  # Last 5 trades
            avg_performance = sum(recent_trades) / len(recent_trades)
            
            # VERY aggressive scaling on winning streaks
            if avg_performance > 0.02:  # Winning streak
                risk *= 2.5  # Massive scaling up
            elif avg_performance < -0.02:  # Losing streak
                risk *= 0.6
        
        # Factor 3: Current account performance vs starting balance
        account_performance = (self.balance - self.starting_balance) / self.starting_balance
        if account_performance < -0.10:  # Down more than 10%
            risk *= 0.5  # Be more conservative
        elif account_performance > 0.20:  # Up more than 20%
            risk *= 2.0  # VERY aggressive - compound wins hard
        
        # Ensure risk stays within reasonable bounds (10% to 80% for aggressive but realistic trading)
        # Allow hot streaks to scale up significantly, but prevent unrealistic over-leverage
        risk = max(0.10, min(0.80, risk))  # Changed from 1.0 to 0.80
        
        return risk

    def calculate_position_size(self, price: float):
        # Risk % of account per trade - supports fractional shares
        capital_to_use = self.balance * self.risk_per_trade
        if price <= 0:
            return 0
        return capital_to_use / price

    def run(self, data: pd.DataFrame, ticker: str = "UNKNOWN"):
        if self.current_strategy is None:
            raise Exception("No strategy selected.")
        signals = self.current_strategy.generate_signal(data)

        # Reset indices to ensure alignment
        data_reset = data.reset_index(drop=True)
        signals_reset = signals.reset_index(drop=True)

        # Apply paper trading logic
        for i in range(len(data_reset)):
            signal = signals_reset.iloc[i]['Signal']
            price = data_reset.iloc[i]['Close']
            
            # Track portfolio state at each step (for plotting)
            position_value = self.position * price if self.position > 0 else 0
            portfolio_value = self.balance + position_value
            self.balance_history.append(self.balance)
            self.shares_history.append(self.position)
            self.portfolio_value_history.append(portfolio_value)

            # Check for take profit or stop loss if we have an open position
            if self.position > 0 and ticker in self.activePositions:
                position_data = self.activePositions[ticker]
                profit_percent = (price - position_data['entry_price']) / position_data['entry_price']
                
                # Take profit
                if profit_percent >= self.take_profit_percent:
                    self.balance += position_data['shares'] * price
                    self.balance = self.round_down(self.balance)
                    # Track trade performance
                    self.trade_history.append(profit_percent)
                    self.win_streak += 1
                    self.loss_streak = 0
                    del self.activePositions[ticker]
                    # Track executed sell (take profit)
                    self.executed_trades.append({'index': i, 'action': 'SELL', 'price': price})
                    self.position = 0
                    self.position_price = 0
                    continue
                
                # Stop loss
                if profit_percent <= -self.stop_loss_percent:
                    self.balance += position_data['shares'] * price
                    self.balance = self.round_down(self.balance)
                    # Track trade performance
                    self.trade_history.append(profit_percent)
                    self.loss_streak += 1
                    self.win_streak = 0
                    del self.activePositions[ticker]
                    # Track executed sell (stop loss)
                    self.executed_trades.append({'index': i, 'action': 'SELL', 'price': price})
                    self.position = 0
                    self.position_price = 0
                    continue

            # Buy signal
            if signal == 1 and self.position == 0:
                # Calculate dynamic risk before sizing position
                self.risk_per_trade = self.calculate_dynamic_risk(data_reset, i)
                size = self.calculate_position_size(price)
                
                # SAFETY CHECK: Never buy more than available balance
                max_affordable_shares = self.balance / price
                size = min(size, max_affordable_shares)
                
                if size > 0 and (size * price) <= self.balance:
                    self.position = size
                    self.position_price = price
                    self.activePositions[ticker] = {
                        'shares': size,
                        'entry_price': price
                    }
                    self.balance -= size * price
                    self.balance = self.round_down(self.balance)
                    # Track executed buy
                    self.executed_trades.append({'index': i, 'action': 'BUY', 'price': price})

            # Sell signal
            elif signal == -1 and self.position > 0:
                profit_percent = (price - self.position_price) / self.position_price
                self.balance += self.position * price
                self.balance = self.round_down(self.balance)
                # Track trade performance
                self.trade_history.append(profit_percent)
                if profit_percent > 0:
                    self.win_streak += 1
                    self.loss_streak = 0
                else:
                    self.loss_streak += 1
                    self.win_streak = 0
                if ticker in self.activePositions:
                    del self.activePositions[ticker]
                # Track executed sell
                self.executed_trades.append({'index': i, 'action': 'SELL', 'price': price})
                self.position = 0
                self.position_price = 0

        # Close any open position at the end with final price
        if self.position > 0:
            final_price = data_reset.iloc[-1]['Close']
            profit_percent = (final_price - self.position_price) / self.position_price
            self.balance += self.position * final_price
            self.balance = self.round_down(self.balance)
            self.trade_history.append(profit_percent)
            if ticker in self.activePositions:
                del self.activePositions[ticker]
            # Track executed sell (final close)
            self.executed_trades.append({'index': len(data_reset) - 1, 'action': 'SELL', 'price': final_price})
            self.position = 0
            self.position_price = 0

        return {
            "final_balance": self.balance,
            "open_position": self.position,
            "position_entry_price": self.position_price,
            "active_positions": self.activePositions.copy(),
            "total_trades": len(self.trade_history),
            "winning_trades": sum(1 for t in self.trade_history if t > 0),
            "signals": signals
        }
    
def get_yf_candles(symbol="AAPL", interval="1d", period="1y"):
    df = yf.download(symbol, interval=interval, period=period)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join(filter(None, col)).strip() for col in df.columns.values]

    rename_map = {c: c.split('_')[0] for c in df.columns}
    df = df.rename(columns=rename_map)
    df = df[['Open','High','Low','Close','Volume']].reset_index()

    df.dropna(inplace=True)
    return df

if __name__ == "__main__":
    symbol = "AAPL"
    data = get_yf_candles(symbol)

    starting_balance = 1000
    # Base risk will be adjusted dynamically based on market conditions
    bot = TradingBot(
        starting_balance=starting_balance,
        risk_per_trade=0.30,
        take_profit_percent=0.30,
        stop_loss_percent=0.03, 
        dynamic_risk=True
    )

    bot.set_strategy("ma_crossover")
    result = bot.run(data, ticker=symbol)
    
    # Display results with trade statistics
    profit_loss = result['final_balance'] - starting_balance
    profit_percent = (profit_loss / starting_balance) * 100
    win_rate = (result['winning_trades'] / result['total_trades'] * 100) if result['total_trades'] > 0 else 0
    
    print(f"Paper Trading End Balance: ${result['final_balance']:.2f} Starting from ${starting_balance}")
    print(f"Profit/Loss: ${profit_loss:.2f} ({profit_percent:.2f}%)")
    print(f"Total Trades: {result['total_trades']}")
    print(f"Winning Trades: {result['winning_trades']} ({win_rate:.1f}% win rate)")
    print(f"Active Positions: {result['active_positions']}")
    bot.plot_trades(data, result['signals'], starting_balance, result['final_balance'])


