from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from MultiStockTraderInstance import MultiStockTradeStatus
from time import time
import dotenv
import os
import random
import json
from bcrypt import hashpw, gensalt, checkpw

dotenv.load_dotenv(".env")

def CreateInterface(state: MultiStockTradeStatus) -> Flask:
    app = Flask(__name__, template_folder='Pages')
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.secret_key = GetFlaskSecretKey()
    app.permanent_session_lifetime = 120
    # track active logins and their expiry times
    app.active_logins = {}

    @app.route('/')
    def home():
        #Check If A Credentials File Exists
        if(os.path.exists("Web_Interface/Credentials/Credentials.json")):
            return redirect(url_for('login_page'))
        else:
            return redirect(url_for('setup_page'))
        
    @app.route('/login', methods=['GET'])
    def login_page():
        return render_template('Login.html')
    

    @app.route('/login', methods=['POST'])
    def login():
        # Validate The Credentials
        username = request.form.get('username')
        password = request.form.get('password')

        if CheckLoginCredentials(username, password):
            session['username'] = username
            session['premissions'] = GetUserPermissions(username)

            #Check If We Got Any Permissions
            if session['premissions'] is None:
                session.pop('username', None)
                return "User Has No Permissions Assigned", 403
            
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            # Render the login page with an error message so it can be displayed inline
            return render_template('Login.html', error='Invalid username/password')
    
    @app.route('/setup', methods=['GET'])
    def setup_page():
        return render_template('Setup.html')
    
    @app.route('/addUser', methods=['GET'])
    def addUser_page():
        if(session.get('username') is None):
            return redirect(url_for('home'))

        return render_template('AddUser.html')
    
    @app.route('/addUser', methods=['POST'])
    def addUser():
        # Get Details From The Form
        userDetails = {
            request.form.get("username"): {
                "password": hashpw(request.form.get('password').encode('utf-8'), GetSalt()).decode('utf-8')
            }
        }

        #Check If The Credentials File Exists
        if os.path.exists("Web_Interface/Credentials/Credentials.json"):
            #Check The Users premissions
            if session.get('premissions') != "root":
                return render_template('AddUser.html', message='Invalid access premissions', success=False)
            
            #Load Existing Credentials
            try:
                with open("Web_Interface/Credentials/Credentials.json", "r") as f:
                    existingCredentials = json.load(f)
            except Exception as e:
                return render_template('AddUser.html', message='Failed to read credentials file', success=False)
            
            #Add New User Details
            existingCredentials[request.form.get("username")] = userDetails[request.form.get("username")]
            existingCredentials[request.form.get("username")]["permissions"] = request.form.get("Access_Level", "user")

            #Write Updated Credentials Back To File
            try:
                with open("Web_Interface/Credentials/Credentials.json", "w") as f:
                    json.dump(existingCredentials, f)
            except Exception as e:
                return render_template('AddUser.html', message='Failed to write credentials', success=False)
            
            return render_template('AddUser.html', message='User updated', success=True)
        else:
            #Make The Credentials Directory
            os.makedirs("Web_Interface/Credentials", exist_ok=True)

            #Give All Permissions To The First User
            userDetails[request.form.get("username")]["permissions"] = "root"

            #Allow First Time User Creation
            try:
                with open("Web_Interface/Credentials/Credentials.json", "w") as f:
                    json.dump(userDetails, f)
            except Exception as e:
                return f"Failed To Write Credentials: {e}", 500

        # Show a confirmation message on the add-user page after first-user creation
        return render_template('Login.html')

    @app.route('/logout', methods=['POST'])
    def logout():
        session.pop('username', None)
        return redirect(url_for('home'))

    @app.route('/dashboard')
    def dashboard():
        if(session.get('username') is None):
            return redirect(url_for('home'))
        
        # ensure the session has an expires timestamp for the client
        if not session.get('login_expires'):
            expires = int(time()) + int(app.permanent_session_lifetime.total_seconds())
            session['login_expires'] = expires
            app.active_logins[session['username']] = expires

        data = state.SnapshotData()
        return render_template('HomePage.html', data=data)

    @app.route('/dashboard/stock/<ticker>')
    def stock_detail(ticker):
        if(session.get('username') is None):
            return redirect(url_for('home'))

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
    print(f"Stored Password: {storedPassword}")

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