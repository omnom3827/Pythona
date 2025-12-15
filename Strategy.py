import pandas as pd
import math

# -----------------------------
# Shared Risk Calculation Mixin
# -----------------------------
class RiskCalculatorMixin:
    """Mixin providing calculate_risk method for all strategies"""
    
    def _atr(self, data: pd.DataFrame, n: int = 14) -> pd.Series:
        """Simple ATR implementation (returns rolling mean of True Range)."""
        high = data['High']
        low = data['Low']
        close = data['Close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(n, min_periods=1).mean()

    def calculate_risk(self, data: pd.DataFrame, idx: int, *,
                       current_capital: float = 0.0, current_shares: float = 0.0,
                       mode: str = "buy",
                       base_risk: float = 0.05, k_atr: float = 3.0,
                       min_risk: float = 0.01, max_risk: float = 0.20) -> tuple[float, float]:
        """
        Return risk factor in [0,1] and suggested shares to buy/sell (up to 2dp fractional) for the trade at bar `idx`.

        Returns:
            (risk_factor, suggested_shares)
            - risk_factor: 0.0 = very low risk (conservative), 0.5 = neutral, 1.0 = very high risk (aggressive).
            - suggested_shares: recommended number of shares to buy (mode="buy") or sell (mode="sell"), rounded to 2dp.

        The factor is computed from an ATR-based baseline risk_pct, adjusted by short/long volatility
        regime, trend strength, position concentration, and available capital, then normalized into [0,1].

        Args:
            current_capital: Available cash (not invested).
            current_shares: Number of shares currently held in this position (allows fractional).
            mode: "buy" to calculate shares to buy, "sell" to calculate shares to sell.
        """
        # Bounds and basic checks
        if idx < 0 or idx >= len(data):
            return (0.0, 0.0)

        price = float(data.iloc[idx]['Close'])
        if price <= 0:
            return (0.0, 0.0)

        # ATR-based stop distance (used only to scale risk)
        atr_series = self._atr(data, n=14)
        atr_val = float(atr_series.iloc[idx]) if not pd.isna(atr_series.iloc[idx]) else 0.0

        # Volatility regime: compare short vs long realized vol
        short_vol = data['Close'].pct_change().rolling(10).std().iloc[idx]
        long_vol = data['Close'].pct_change().rolling(50).std().iloc[idx]
        vol_adj = 1.0
        try:
            if pd.notna(short_vol) and pd.notna(long_vol) and long_vol > 0:
                if short_vol > 1.2 * long_vol:
                    vol_adj = 0.6
                elif short_vol < 0.8 * long_vol:
                    vol_adj = 1.2
        except Exception:
            vol_adj = 1.0

        # Trend strength: use strategy-specific trend measure if available
        trend_adj = self._get_trend_adjustment(data, idx, price)

        # Position concentration adjustment: reduce risk if already heavily invested
        position_value = current_shares * price
        total_equity = current_capital + position_value
        concentration_adj = 1.0
        if total_equity > 0:
            concentration = position_value / total_equity
            if concentration > 0.7:  # > 70% in this position
                concentration_adj = 0.5  # very conservative
            elif concentration > 0.5:  # > 50%
                concentration_adj = 0.7
            elif concentration > 0.3:  # > 30%
                concentration_adj = 0.9
            elif concentration < 0.1:  # < 10% (low exposure)
                concentration_adj = 1.2  # allow more aggressive sizing

        # Available capital adjustment: INCREASE risk when high cash available
        # Modified for multi-stock portfolios: only apply when cash is EXTREMELY low
        # This allows each stock trader to use its allocated balance independently
        capital_adj = 1.0
        if total_equity > 0:
            cash_pct = current_capital / total_equity
            # Only reduce risk when cash is critically low (nearly fully invested)
            # This prevents multi-stock scenarios from being overly conservative
            if cash_pct < 0.05:  # < 5% cash (critically low)
                capital_adj = 0.7  # Conservative - preserve remaining cash
            elif cash_pct < 0.10:  # < 10% cash (very low)
                capital_adj = 0.85  # Slightly conservative
            # Otherwise maintain neutral capital_adj = 1.0
            # This treats each trader's allocation as independent

        # Compose adjustments and compute a heuristic risk_pct
        adj = vol_adj * trend_adj * concentration_adj * capital_adj
        adj = max(0.3, min(2.5, adj))
        risk_pct = base_risk * adj
        risk_pct = max(min_risk, min(max_risk, risk_pct))

        # Normalize risk_pct to [0,1] based on min/max
        denom = max(1e-9, (max_risk - min_risk))
        normalized = (risk_pct - min_risk) / denom
        normalized = max(0.0, min(1.0, normalized))

        # Calculate suggested shares based on PERCENTAGE of capital
        # This ensures that $100 and $10,000 behave proportionally the same
        suggested_shares = 0.0
        
        if mode.lower() == "sell":
            # SELL mode: suggest how many shares to sell
            # Higher risk factor = more aggressive exit (sell more)
            # Use risk factor to scale from partial to full exit
            if current_shares > 0:
                # Base sell: proportional to risk factor (0.5 = sell 50%, 1.0 = sell 100%)
                sell_pct = 0.5 + (normalized * 0.5)  # maps [0,1] → [0.5, 1.0] (sell 50%-100%)
                suggested_shares = current_shares * sell_pct
                # Round to 2 decimal places
                suggested_shares = round(min(suggested_shares, current_shares), 2)
        else:
            # BUY mode: suggest how many shares to buy
            # Use risk_pct as the percentage of AVAILABLE CAPITAL to deploy
            # This makes it scale-invariant: 1% of $100 = $1, 1% of $10,000 = $100
            if current_capital > 0 and price > 0:
                dollar_amount = current_capital * risk_pct
                suggested_shares = dollar_amount / price
                
                # CRITICAL: Cap by available capital to prevent overspending
                # This ensures we NEVER suggest buying more than cash allows
                max_affordable = current_capital / price
                suggested_shares = min(suggested_shares, max_affordable)
                
                # Additional safety check: ensure total cost doesn't exceed capital
                total_cost = suggested_shares * price
                if total_cost > current_capital:
                    # Reduce shares to exactly match available capital
                    suggested_shares = current_capital / price
                
                # Round to 2 decimal places
                suggested_shares = round(suggested_shares, 2)
                
                # Final validation: ensure rounded value still fits within capital
                if suggested_shares * price > current_capital:
                    suggested_shares = max(0.0, suggested_shares - 0.01)

        return (float(normalized), float(suggested_shares))

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Override in subclass for strategy-specific trend measurement. Default uses simple SMA distance."""
        try:
            sma_20 = data['Close'].rolling(20).mean().iloc[idx]
            if pd.notna(sma_20) and sma_20 > 0:
                dist = abs(price - sma_20) / sma_20
                if dist > 0.03:
                    return 1.1
                elif dist < 0.005:
                    return 0.9
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 1: Moving Average Crossover
# -----------------------------
class MovingAverageCrossover(RiskCalculatorMixin):
    def __init__(self, short_window=50, long_window=200):
        self.name = "Moving Average Crossover"
        self.short_window = short_window
        self.long_window = long_window
    
    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use long SMA distance for trend strength"""
        try:
            sma_long = data['Close'].rolling(self.long_window).mean().iloc[idx]
            if pd.notna(sma_long) and sma_long > 0:
                dist = abs(price - sma_long) / sma_long
                if dist > 0.03:
                    return 1.1
                elif dist < 0.005:
                    return 0.9
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 2: RSI Strategy
# -----------------------------
class RSIStrategy(RiskCalculatorMixin):
    def __init__(self, period=14, overbought=70, oversold=30):
        self.name = "RSI Strategy"
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use RSI extremity for trend strength"""
        try:
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[idx]
            if pd.notna(rsi):
                # More extreme RSI = stronger signal
                if rsi < 20 or rsi > 80:
                    return 1.2  # very extreme, strong signal
                elif rsi < 35 or rsi > 65:
                    return 1.1
                elif 45 < rsi < 55:
                    return 0.8  # near neutral, weak signal
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 3: Breakout Strategy
# -----------------------------
class BreakoutStrategy(RiskCalculatorMixin):
    def __init__(self, window=20):
        self.name = "Breakout Strategy"
        self.window = window

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Measure distance from recent range"""
        try:
            high_max = data['High'].rolling(self.window).max().iloc[idx]
            low_min = data['Low'].rolling(self.window).min().iloc[idx]
            if pd.notna(high_max) and pd.notna(low_min) and high_max > low_min:
                range_size = high_max - low_min
                mid = (high_max + low_min) / 2
                dist_from_mid = abs(price - mid) / range_size
                if dist_from_mid > 0.4:  # near edge = strong breakout
                    return 1.2
                elif dist_from_mid < 0.1:  # near middle = weak
                    return 0.8
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 4: Volume Spike Strategy
# -----------------------------
class VolumeSpikeStrategy(RiskCalculatorMixin):
    def __init__(self, multiplier=2):
        self.name = "Volume Spike Strategy"
        self.multiplier = multiplier

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use volume spike magnitude for trend strength"""
        try:
            avg_vol = data['Volume'].rolling(20).mean().iloc[idx]
            current_vol = data['Volume'].iloc[idx]
            if pd.notna(avg_vol) and pd.notna(current_vol) and avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                if vol_ratio > 3:  # 3x average = very strong
                    return 1.3
                elif vol_ratio > 2:
                    return 1.1
                elif vol_ratio < 0.5:  # low volume = weak
                    return 0.7
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 5: MACD Strategy
# -----------------------------
class MACDStrategy(RiskCalculatorMixin):
    def __init__(self, fast=12, slow=26, signal=9):
        self.name = "MACD Strategy"
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use MACD histogram magnitude for trend strength"""
        try:
            exp1 = data['Close'].ewm(span=self.fast, adjust=False).mean().iloc[idx]
            exp2 = data['Close'].ewm(span=self.slow, adjust=False).mean().iloc[idx]
            if pd.notna(exp1) and pd.notna(exp2):
                macd = exp1 - exp2
                macd_pct = abs(macd) / price if price > 0 else 0
                if macd_pct > 0.02:
                    return 1.2
                elif macd_pct > 0.01:
                    return 1.1
                elif macd_pct < 0.002:
                    return 0.8
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 6: Bollinger Bands Strategy
# -----------------------------
class BollingerBandsStrategy(RiskCalculatorMixin):
    def __init__(self, window=20, num_std=2):
        self.name = "Bollinger Bands Strategy"
        self.window = window
        self.num_std = num_std

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use band width and position within bands for trend strength"""
        try:
            sma = data['Close'].rolling(self.window).mean().iloc[idx]
            std = data['Close'].rolling(self.window).std().iloc[idx]
            if pd.notna(sma) and pd.notna(std) and std > 0:
                # Distance from mean
                z_score = abs(price - sma) / std
                
                if z_score > 2:  # Near or beyond bands = strong signal
                    return 1.2
                elif z_score > 1.5:
                    return 1.1
                elif z_score < 0.5:  # Near mean = weak signal
                    return 0.8
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 7: Momentum Strategy
# -----------------------------
class MomentumStrategy(RiskCalculatorMixin):
    def __init__(self, lookback=14, threshold=0.02):
        self.name = "Momentum Strategy"
        self.lookback = lookback
        self.threshold = threshold  # 2% momentum threshold

    def GetSignals(self, data: pd.DataFrame):
        # Calculate momentum (rate of change)
        data['Momentum'] = data['Close'].pct_change(self.lookback)
        data['Signal'] = 0
        
        # Only signal when momentum crosses thresholds
        prev_momentum = data['Momentum'].shift(1)
        
        # Momentum crosses ABOVE positive threshold = BUY (strong upward momentum)
        data.loc[(prev_momentum <= self.threshold) & (data['Momentum'] > self.threshold), 'Signal'] = 1
        
        # Momentum crosses BELOW negative threshold = SELL (strong downward momentum)
        data.loc[(prev_momentum >= -self.threshold) & (data['Momentum'] < -self.threshold), 'Signal'] = -1
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use momentum magnitude for trend strength"""
        try:
            momentum = data['Close'].pct_change(self.lookback).iloc[idx]
            if pd.notna(momentum):
                abs_momentum = abs(momentum)
                if abs_momentum > 0.05:  # >5% momentum = very strong
                    return 1.3
                elif abs_momentum > 0.03:
                    return 1.1
                elif abs_momentum < 0.01:  # <1% = weak
                    return 0.8
        except Exception:
            pass
        return 1.0


# -----------------------------
# Strategy 8: Mean Reversion Strategy
# -----------------------------
class MeanReversionStrategy(RiskCalculatorMixin):
    def __init__(self, window=20, std_threshold=1.5):
        self.name = "Mean Reversion Strategy"
        self.window = window
        self.std_threshold = std_threshold

    def GetSignals(self, data: pd.DataFrame):
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
        
        return data[['Datetime', 'Close', 'Signal']]

    def _get_trend_adjustment(self, data: pd.DataFrame, idx: int, price: float) -> float:
        """Use Z-score extremity for trend strength (mean reversion context)"""
        try:
            sma = data['Close'].rolling(self.window).mean().iloc[idx]
            std = data['Close'].rolling(self.window).std().iloc[idx]
            if pd.notna(sma) and pd.notna(std) and std > 0:
                z_score = abs((price - sma) / std)
                if z_score > 2.5:  # Very extreme = strong reversion signal
                    return 1.3
                elif z_score > 2:
                    return 1.2
                elif z_score < 1:  # Near mean = weak signal
                    return 0.7
        except Exception:
            pass
        return 1.0


# Registry of strategies
strategies = {
    "MAC": MovingAverageCrossover,
    "RSI": RSIStrategy,
    "Breakout": BreakoutStrategy,
    "VolumeSpike": VolumeSpikeStrategy,
    "MACD": MACDStrategy,
    "BollingerBands": BollingerBandsStrategy,
    "Momentum": MomentumStrategy,
    "MeanReversion": MeanReversionStrategy,
}