from threading import Lock
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from MultiStockTraderInstance import MultiStockTradeStatus
from time import time
import dotenv
#Blueprints
from Web_Interface.Blueprints.LoginPage import create_auth_blueprint
from Web_Interface.Blueprints.Stock import create_stock_blueprint
#Functions
from Web_Interface.Functions.Auth import GetFlaskSecretKey

dotenv.load_dotenv(".env")

def CreateInterface(state: MultiStockTradeStatus) -> Flask:
    app = Flask(__name__, template_folder='Pages')

    # Disable cache for static files
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # Session configuration
    app.secret_key = GetFlaskSecretKey()
    app.permanent_session_lifetime = 120

    # Track active logins
    app.active_logins = {}
    app.active_logins_lock = Lock()

    # Add Blueprints
    auth_bp = create_auth_blueprint(state)
    app.register_blueprint(auth_bp)
    stock_bp = create_stock_blueprint(state)
    app.register_blueprint(stock_bp)

    @app.route('/dashboard')
    def dashboard():
        if(session.get('username') is None):
            return redirect(url_for('auth.home'))
        
        # ensure the session has an expires timestamp for the client
        if not session.get('login_expires'):
            expires = int(time()) + int(app.permanent_session_lifetime.total_seconds())
            session['login_expires'] = expires

            with app.active_logins_lock:
                app.active_logins[session['username']] = expires

        data = state.SnapshotData()
        return render_template('HomePage.html', data=data)

    @app.route('/dashboard/stock/<ticker>')
    def stock_detail(ticker):
        if(session.get('username') is None):
            return redirect(url_for('auth.home'))

        data = state.SnapshotData()
        stocks = data.get('Stocks', {})
        selected = None
        for key, val in stocks.items():
            if key.lower() == ticker.lower():
                selected = (key, val)
                break
        if selected is None:
            return render_template('StockDetail.html', ticker=ticker, stock=None)
        # pass the ticker (readable) and the stock dictionary
        return render_template('StockDetail.html', ticker=selected[0], stock=selected[1])
    
    @app.route('/stock/<ticker>/optimiser', methods=['POST'])
    def stock_optimiser(ticker):
        print(f"Stock optimiser requested for {ticker}")
        # TODO: hook into StockOptimiser / backtester
        state.UpdateStockInstructions(ticker, {"optimiser_requested": True})

        return jsonify(message='optimiser started'), 200

    @app.route('/stock/<ticker>/backtest', methods=['POST'])
    def stock_backtest(ticker):
        print(f"Stock Backtest Requested For {ticker}")

        state.UpdateStockInstructions(ticker, {"backtest_requested": True})

        return jsonify(message='backtest started'), 200

    @app.route('/stock/<ticker>/apply_config', methods=['POST'])
    def stock_apply_config(ticker):
        try:
            payload = request.get_json() or {}
        except Exception:
            payload = {}

        print(f"Apply config requested for {ticker}: {payload}")

        state.UpdateStockInstructions(ticker, {"config_updates": payload})

        return jsonify(message='config update applied'), 200

    @app.route('/add_stock')
    def add_stock_page():
        if session.get('username') is None:
            return redirect(url_for('auth.home'))
        
        return render_template('AddStock.html')

    @app.route('/api/pending/seen', methods=['POST'])
    def MakeStockFailAsSeen():
        if session.get('username') is None:
            return jsonify(message='Unauthorized'), 401

        data = request.get_json() or {}
        ticker = data.get('ticker')
        if not ticker:
            return jsonify(message='Ticker not provided'), 400

        print(f"Pending Stock {ticker} Has Been Marked As Seen By {session['username']}. Removing From Pending List.")
        state.RemovePendingStock(ticker)
        return jsonify(message='Pending stock marked as seen'), 200

    return app