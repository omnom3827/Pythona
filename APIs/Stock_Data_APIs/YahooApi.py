import yfinance as yf
import pandas as pd

class Yahoo:
    def GetStockData(self, ticker: str, period: str, interval: str):
        data = yf.download(ticker.split("_")[0], interval=interval, period=period, auto_adjust=True)

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