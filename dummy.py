# tools/bench_runner.py
import sys, time
from APIs.BackTestBroker import BackTestBroker
from StockTrader import StockTrader
# adjust params as needed:
TICKER = "AAPL_US_EQ"
BALANCE = 10000.0
INTERVAL="1h"
PERIOD="1y"
STOP=0.05
TP=0.25
TRAIL=0.15

def run_backtest_broker():
    bt = BackTestBroker(ticker=TICKER, startingBalance=BALANCE, period=PERIOD, interval=INTERVAL,
                        stopLossPercent=STOP, takeProfitPercent=TP, trailingStopPercent=TRAIL)
    t0 = time.perf_counter()
    bt.RunBackTest()
    return time.perf_counter() - t0

def run_stocktrader_old():
    # create minimal StockTrader that calls UpdateStrategy(newMethod=False)
    # ensure dependencies (stockMultiHandler, broker, stocksApi) are mocked or passed as in your app
    from MultiStockTraderHandler import DummyHandlerForBench  # or construct minimal handler
    dummy_handler = DummyHandlerForBench()
    st = StockTrader(ticker=f"{TICKER}", balance=BALANCE, stockMultiHandler=dummy_handler,
                     broker=dummy_handler.broker, stocksApi=dummy_handler.stocksApi,
                     stockDataInterval=INTERVAL, stockDataPeriod=PERIOD,
                     stopLossPercent=STOP, takeProfitPercent=TP, trailingStopPercent=TRAIL)
    t0 = time.perf_counter()
    st.UpdateStrategy(newMethod=False)
    return time.perf_counter() - t0

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv)>1 else "backtest_broker"
    if mode == "warmup":
        run_backtest_broker(); run_stocktrader_old(); print("0.0")
    elif mode == "backtest_broker":
        print(f"{run_backtest_broker():.6f}")
    elif mode == "stocktrader_old":
        print(f"{run_stocktrader_old():.6f}")
    else:
        print("0.0")