from threading import Thread
from MultiStockTraderInstance import MultiStockTradeStatus
from MultiStockTraderHandler import MultiStockTraderHandler
from Web_Interface.PythonaFlaskWeb import CreateInterface
from waitress import serve
from SaveConfig import LoadFromConfig

instance = MultiStockTradeStatus()
useWebInterface = True

#Loading Config From File
loadedConfig = LoadFromConfig()

if useWebInterface:
    handler = MultiStockTraderHandler(
        **loadedConfig,
        instance=instance
    )

    multiStockTraderThread = Thread(
        target=handler.RunUpdateLoop, 
        daemon=True
    )

    multiStockTraderThread.start()

    app = CreateInterface(instance)
    serve(app, host='0.0.0.0', port=5000)
else:
    MultiStockTraderHandler(
        **loadedConfig,
    ).RunUpdateLoop()