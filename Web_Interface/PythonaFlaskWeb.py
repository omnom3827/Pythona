from threading import Lock
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from MultiStockTraderInstance import MultiStockTradeStatus
from time import time
import dotenv
import os
import random
import json
from bcrypt import hashpw, gensalt, checkpw
#Blueprints
from Web_Interface.Blueprints.LoginPage import create_auth_blueprint

dotenv.load_dotenv(".env")

def CreateInterface(state: MultiStockTradeStatus) -> Flask:
    app = Flask(__name__, template_folder='Pages')

    # Disable cache for static files
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # Session configuration
    app.secret_key = GetFlaskSecretKey()
    app.permanent_session_lifetime = 120

    # Track active logins (thread-safe)
    app.active_logins = {}
    app.active_logins_lock = Lock()

    # Add Blueprints
    auth_bp = create_auth_blueprint(state)
    app.register_blueprint(auth_bp)

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
        stocks = data.get('Stocks', {}) if data else {}
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

    return app

def GetFlaskSecretKey() -> str:
    key = os.getenv("WEB_INTERFACE_KEY", None)

    # Check If We Have A Secret Key
    if key is None or len(key) == 0:
        print("No Flask Key Found. Generating Key...")
        charSet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        key = ""
        for i in range(32):
            key += random.choice(charSet)
        
        # Write The Key To The .env File
        try:
            with open(".env", "a") as f:
                f.write(f"\nWEB_INTERFACE_KEY=\"{key}\"\n")
            print("Flask Key Written To .env File.")
        except Exception as e:
            print(f"Failed To Write Flask Key To .env File: {e}. Using Generated Key For This Session Only.")

        return key
    else:
        return key
    
def GetSalt() -> bytes:
    salt = os.getenv("BCRYPT_SALT", None)

    # Check If We Have A Salt
    if salt is None or len(salt) == 0:
        print("No Bcrypt Salt Found. Generating Salt...")
        salt = gensalt()
        # Write The Salt To The .env File
        try:
            with open(".env", "a") as f:
                f.write(f"\nBCRYPT_SALT=\"{salt.decode('utf-8')}\"\n")
            print("Bcrypt Salt Written To .env File.")
        except Exception as e:
            print(f"Failed To Write Bcrypt Salt To .env File: {e}. Using Generated Salt For This Session Only.")

        return salt
    else:
        return salt.encode('utf-8')
    
def CheckLoginCredentials(username: str, password: str) -> bool:
    #Load The Credentials File
    try:
        with open("Web_Interface/Credentials/Credentials.json", "r") as f:
            credentials = json.load(f)
    except Exception as e:
        print(f"Failed To Load Credentials File: {e}")
        return False

    # Check username
    if credentials.get(username, None) is None:
        print(f"{username} Not Found In Credentials File")
        return False

    storedPassword = credentials.get(username)["password"]

    # Verify password using bcrypt.checkpw
    try:
        if isinstance(storedPassword, str):
            storedPassword = storedPassword.encode('utf-8')
        return checkpw(password.encode('utf-8'), storedPassword)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False
    
def GetUserPermissions(username: str) -> str:
    #Load The Credentials File
    try:
        with open("Web_Interface/Credentials/Credentials.json", "r") as f:
            credentials = json.load(f)
    except Exception as e:
        print(f"Failed To Load Credentials File: {e}")
        return None
    
    # Check username
    if credentials.get(username, None) == None:
        return None

    return credentials.get(username)["permissions"]