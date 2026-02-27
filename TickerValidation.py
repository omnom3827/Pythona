def ValidateTicker(ticker: str, stockApi, brokerApi) -> bool:
    data = stockApi.GetStockData(ticker.split("_")[0], interval="1h", period="1y")

    # Check If Data Is Not Empty
    if data is None:
        print(f"Validation Failed: No data returned for ticker {ticker}")
        return False
    
    # Check If Broker API Has This Ticker
    data = brokerApi.GetOpenPositions(ticker)

    if data is None:
        print(f"Validation Failed: Broker API does not recognize ticker {ticker}")
        return False

    return True