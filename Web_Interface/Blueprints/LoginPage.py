from flask import Blueprint, render_template, redirect, url_for, request, session
import os
import json
from bcrypt import hashpw
from Web_Interface.Functions.Auth import CheckLoginCredentials, GetUserPermissions, GetSalt

def create_auth_blueprint(state):
	auth = Blueprint('auth', __name__)

	@auth.route('/')
	def home():
		if os.path.exists("Web_Interface/Credentials/Credentials.json"):
			return redirect(url_for('auth.login_page'))
		else:
			return redirect(url_for('auth.setup_page'))

	@auth.route('/login', methods=['GET'])
	def login_page():
		return render_template('Login.html')

	@auth.route('/login', methods=['POST'])
	def login():
		username = request.form.get('username')
		password = request.form.get('password')

		if CheckLoginCredentials(username, password):
			session['username'] = username
			session['premissions'] = GetUserPermissions(username)

			if session['premissions'] is None:
				session.pop('username', None)
				return "User Has No Permissions Assigned", 403

			session.permanent = True
			return redirect(url_for('dashboard'))
		else:
			return render_template('Login.html', error='Invalid username/password')

	@auth.route('/setup', methods=['GET'])
	def setup_page():
		return render_template('Setup.html')

	@auth.route('/addUser', methods=['GET'])
	def addUser_page():
		if session.get('username') is None:
			return redirect(url_for('auth.home'))

		return render_template('AddUser.html')

	@auth.route('/addUser', methods=['POST'])
	def addUser():
		userDetails = {
			request.form.get("username"): {
				"password": hashpw(request.form.get('password').encode('utf-8'), GetSalt()).decode('utf-8')
			}
		}

		if os.path.exists("Web_Interface/Credentials/Credentials.json"):
			if session.get('premissions') != "root":
				return render_template('AddUser.html', message='Invalid access premissions', success=False)

			try:
				with open("Web_Interface/Credentials/Credentials.json", "r") as f:
					existingCredentials = json.load(f)
			except Exception:
				return render_template('AddUser.html', message='Failed to read credentials file', success=False)

			existingCredentials[request.form.get("username")] = userDetails[request.form.get("username")]
			existingCredentials[request.form.get("username")]["permissions"] = request.form.get("Access_Level", "user")

			try:
				with open("Web_Interface/Credentials/Credentials.json", "w") as f:
					json.dump(existingCredentials, f)
			except Exception:
				return render_template('AddUser.html', message='Failed to write credentials', success=False)

			return render_template('AddUser.html', message='User updated', success=True)
		else:
			os.makedirs("Web_Interface/Credentials", exist_ok=True)
			userDetails[request.form.get("username")]["permissions"] = "root"

			try:
				with open("Web_Interface/Credentials/Credentials.json", "w") as f:
					json.dump(userDetails, f)
			except Exception as e:
				return f"Failed To Write Credentials: {e}", 500

		return render_template('Login.html')

	@auth.route('/logout', methods=['POST'])
	def logout():
		session.pop('username', None)
		return redirect(url_for('auth.home'))

	return auth