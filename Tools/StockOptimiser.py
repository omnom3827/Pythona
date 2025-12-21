from itertools import product
import time
from APIs.BackTestBroker import BackTestBroker as BackTester

class StockOptimiser:
    def __init__(self, tickers: list[str], initial_balance: float, period: str, interval: str, stockDataApi = None):
        self.tickers = tickers
        self.balance = initial_balance
        self.activeTrades = {}

        # Values To Test Against
        self.param_grid = {
            'takeProfitPercent': [0.08, 0.10, 0.12, 0.15, 0.20, 0.25],  # 8% to 25%
            'stopLossPercent': [0.05, 0.06, 0.08, 0.10, 0.12],  # 5% to 12%
            'trailingStopPercent': [0.08, 0.10, 0.12, 0.15],  # 8% to 15%
            #'base_risk': [0.05, 0.08, 0.10, 0.12],  # 5% to 12% capital per trade
            #'min_risk': [0.01, 0.02, 0.03],  # 1% to 3%
            #'max_risk': [0.25, 0.30, 0.35, 0.40],  # 25% to 40%
        }

        self.dataCache = {}

        # Download Data For All Tickers
        if stockDataApi is None:
            print("No Stock Data API Provided For Optimiser. This Will Significantly Slow Down The Optimisation Process.")
        else:
            for ticker in self.tickers:
                self.dataCache[ticker] = stockDataApi.GetStockData(ticker, period, interval)

        # Update Grid To All Combinations
        self.param_grid = self.GetAllCombinations()
        print(f"Total Combinations To Test: {len(self.param_grid)}")

    def RunOptimisation(self, loggingLevel: int = 2, runtimeHistoryLimit: int = 20):
        runtimeHistory = []
        bestPramsPerTicker = {}
        total_params = len(self.param_grid)

        for idx, params in enumerate(self.param_grid):

            startTime = time.time()
            
            for ticker in self.tickers:
                backtest = BackTester(
                    ticker=ticker,
                    startingBalance=self.balance,
                    period="1y",
                    interval="1h",
                    stopLossPercent=params['stopLossPercent'],
                    takeProfitPercent=params['takeProfitPercent'],
                    trailingStopPercent=params['trailingStopPercent'],
                    # base_risk=params['base_risk'],
                    # min_risk=params['min_risk'],
                    # max_risk=params['max_risk'],
                    cashedData= self.dataCache[ticker] if ticker in self.dataCache else None
                )

                tradingMethod, roi = backtest.RunBackTest(logResults=False)

                if ticker not in bestPramsPerTicker:
                    bestPramsPerTicker[ticker] = {
                        "params": params,
                        "roi": roi,
                        "tradingMethod": tradingMethod
                    }
                elif roi > bestPramsPerTicker[ticker]["roi"]:
                    bestPramsPerTicker[ticker] = {
                        "params": params,
                        "roi": roi,
                        "tradingMethod": tradingMethod
                    }

            totalRuntime = time.time() - startTime

            #Check Runtime History Length
            if len(runtimeHistory) >= runtimeHistoryLimit:
                runtimeHistory.pop(0)
                
            runtimeHistory.append(totalRuntime)


            #Check Logging Level
            if loggingLevel >= 1:
                # Print Up To 50 * Each Meaning 5%
                for t in bestPramsPerTicker:
                    print(f"Best Params For {t}: ROI: {bestPramsPerTicker[t]['roi']:.2f}, Params: {bestPramsPerTicker[t]['params']}")

            # Progress bar: up to 50 stars representing completion percentage
            if loggingLevel >= 0:
                completed_params = idx + 1
                completed_pct = (completed_params / total_params) * 100 if total_params else 0
                num_stars = min(50, int((completed_params / total_params) * 50))
                star_str = '*' * num_stars
                spaces_str = ' ' * (50 - num_stars)
                print(f"Progress: [{star_str}{spaces_str}] {completed_pct:.1f}% complete ({completed_params}/{total_params} params)")
                print(f"Current Estimated Time Remaining: {((sum(runtimeHistory) / len(runtimeHistory)) * (total_params - completed_params)) / 60:.2f} Minutes")

            if loggingLevel >= 2:
                print(f"Current Params: {params}")

        return bestPramsPerTicker

    def GetAllCombinations(self):
        keys = self.param_grid.keys()
        values = self.param_grid.values()

        # Generate all combinations
        combinations = [dict(zip(keys, v)) for v in product(*values)]

        return combinations