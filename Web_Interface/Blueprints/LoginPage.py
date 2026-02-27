from flask import Blueprint, render_template, redirect, url_for, request, session, current_app
import os
import json
from bcrypt import hashpw
from Web_Interface.Functions.Auth import CheckLoginCredentials, GetUserPermissions, GetSalt, GetAllValidUsers

def LoginBlueprint(state):
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
			session['permissions'] = GetUserPermissions(username)

			if session['permissions'] is None:
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
		if session.get('username') is None or session.get('username') not in current_app.config['VALID_USERS']:
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
			if session.get('permissions') != "root" and session.get('username') != request.form.get("username"):
				return render_template('AddUser.html', message='Invalid access permissions', success=False)
			
			#Check We Are Not Overwriting Current Users Access Permissions
			if session.get('username') == request.form.get('username') and session.get('permissions') != request.form.get('permissions', 'user'):
				print(f"UNAUTHORIZED PERMISSIONS CHANGE ATTEMPT: User {session.get('username')} Attempted To Change Their Own Access Permissions From {session.get('permissions')} To {request.form.get('permissions', 'user')}. WE HAVE AUTOMATICALLY BLOCKED THIS ACTION.")
				return render_template('AddUser.html', message='Cannot Change Your Own Access Permissions', success=False)

			try:
				with open("Web_Interface/Credentials/Credentials.json", "r") as f:
					existingCredentials = json.load(f)
			except Exception:
				return render_template('AddUser.html', message='Failed to Read Credentials File', success=False)

			existingCredentials[request.form.get("username")] = userDetails[request.form.get("username")]
			existingCredentials[request.form.get("username")]["permissions"] = request.form.get("permissions", "user")

			try:
				with open("Web_Interface/Credentials/Credentials.json", "w") as f:
					json.dump(existingCredentials, f)
			except Exception:
				return render_template('AddUser.html', message='Failed To Write Credentials', success=False)

			# Update Valid Users List
			current_app.config['VALID_USERS'] = GetAllValidUsers()

			return render_template('AddUser.html', message='User updated', success=True)
		else:
			os.makedirs("Web_Interface/Credentials", exist_ok=True)
			userDetails[request.form.get("username")]["permissions"] = "root"

			try:
				with open("Web_Interface/Credentials/Credentials.json", "w") as f:
					json.dump(userDetails, f)

				# Update Valid Users List
				current_app.config['VALID_USERS'] = GetAllValidUsers()
			except Exception as e:
				return f"Failed To Write Credentials: {e}", 500

		return render_template('Login.html')

	@auth.route('/logout', methods=['POST'])
	def logout():
		session.pop('username', None)
		return redirect(url_for('auth.home'))

	return auth