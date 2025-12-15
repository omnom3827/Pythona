from flask import Flask, render_template
from MultiStockTraderInstance import MultiStockTradeStatus


def CreateInterface(state: MultiStockTradeStatus) -> Flask:
    app = Flask(__name__, template_folder='Pages')
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    @app.route('/')
    def home():
        return render_template('HomePage.html', stocks=state.Snapshot()['Stocks'])
        # return state.Snapshot()['Stocks']

    @app.route('/stock/<ticker>')
    def stock_detail(ticker):
        data = state.Snapshot()
        stocks = data.get('Stocks', {}) if data else {}
        selected = None
        for key, val in stocks.items():
            if key.split('_')[0].lower() == ticker.lower():
                selected = (key, val)
                break
        if selected is None:
            return render_template('StockDetail.html', ticker=ticker, stock=None)
        # pass the ticker (readable) and the stock dictionary
        return render_template('StockDetail.html', ticker=selected[0].split('_')[0], stock=selected[1])

    return app