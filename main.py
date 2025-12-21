from threading import Thread
from MultiStockTraderInstance import MultiStockTradeStatus
from MultiStockTraderHandler import MultiStockTraderHandler
from Web_Interface.PythonaFlaskWeb import CreateInterface
from Tools.StockOptimiser import StockOptimiser

instance = MultiStockTradeStatus()
useWebInterface = True

config = {
    "stockTickers": [
        "AAPL_US_EQ",
        "GOOGL_US_EQ",
        "NVDA_US_EQ",
        "LAES_US_EQ",
        "MSFT_US_EQ",
    ],
}

if useWebInterface:
    handler = MultiStockTraderHandler(
        **config,
        instance=instance
    )

    multiStockTraderThread = Thread(
        target=handler.RunUpdateLoop, 
        daemon=True
    )

    multiStockTraderThread.start()

    print("here")

    app = CreateInterface(instance)
    app.run(debug=False, port=5000, host='0.0.0.0', use_reloader=False)
else:
    MultiStockTraderHandler(
        **config,
    ).RunUpdateLoop()