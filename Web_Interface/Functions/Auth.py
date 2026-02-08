import os
import json
import random
from bcrypt import gensalt, checkpw

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