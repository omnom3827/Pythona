from flask import Flask, render_template
from MultiStockTraderInstance import MultiStockTradeStatus


def CreateInterface(state: MultiStockTradeStatus) -> Flask:
    app = Flask(__name__, template_folder='Pages')
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    @app.route('/')
    def home():
        return render_template('HomePage.html', stocks=state.Snapshot()['Stocks'])
        # return state.Snapshot()['Stocks']

    return app