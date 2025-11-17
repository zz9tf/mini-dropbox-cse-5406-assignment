import os
import jwt
import datetime
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, Response
import requests

app = Flask(__name__)
logger = logging.getLogger(__name__)

METADATA_API = "http://metadata:5005" # metadata service URL
STORAGE_API = "http://storage:5006" # storage service URL
SECRET_KEY = os.environ.get("SECRET_KEY", "supersecretkey") # secret key for JWT - in more secure setup, use env variable


# --- JWT Helpers ---
def encode_token(username):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "exp": now + datetime.timedelta(days=1),
        "iat": now,
        "sub": username
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        return None


# # --- Routes ---
@app.route("/auth/signup", methods=["POST"])
def signup():
    # grab the username and password
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # validate input
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    # hash password before sending to metadata service
    hashed_password = generate_password_hash(password)
    try:
        # send to metadata service
        resp = requests.post(f"{METADATA_API}/users", json={
            "username": username,
            "password": hashed_password
        })

        # check response from metadata service
        if resp.status_code == 201:
            return jsonify({"message": "Signup successful!"}), 201
        elif resp.status_code == 409:
            return jsonify({"error": "Username already exists"}), 409
        else:
            return jsonify({"error": "Metadata service error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/auth/login", methods=["POST"])
def login():
    # grab the username and password
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # validate input
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    try:
        # fetch user from metadata service
        resp = requests.get(f"{METADATA_API}/users/{username}")

        # check the response
        if resp.status_code != 200:
            return jsonify({"error": "Invalid credentials"}), 401

        # if user is found, check password
        user = resp.json()
        stored_hash = user.get("password")
        if stored_hash and check_password_hash(stored_hash, password):
            token = encode_token(username)

            # store the token in the user's session
            return jsonify({"token": token})
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# auth decorator
def require_auth(f):
    def wrapper(*args, **kwargs):
        # grab the header
        auth_header = request.headers.get("Authorization")

        # check if auth header is present and valid
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        
        # decode the token
        token = auth_header.split(" ", 1)[1]
        username = decode_token(token)
        if not username:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.username = username
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# upload file endpoint (uses 2PC to verify all nodes are alive, then executes original HTTP operations)
@app.route("/files/upload", methods=["POST"])
@require_auth
def upload():
    """Upload file with 2PC: verify all nodes are alive via gRPC, then execute original HTTP operations"""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    filename = file.filename
    file_data = file.read()
    
    try:
        import sys
        sys.path.insert(0, '/app')
        sys.path.insert(0, '/app/..')
        from twopc_coordinator import TwoPhaseCommitCoordinator
        
        # Prepare metadata
        metadata = {
            "filename": filename,
            "path": f"/storage/{filename}",
            "size": len(file_data),
            "version": 1
        }
        
        # Execute 2PC: verify nodes alive, then execute original HTTP operations
        coordinator = TwoPhaseCommitCoordinator()
        result = coordinator.execute_2pc_upload(filename, file_data, metadata)
        
        if result['success']:
            # 2PC validated nodes and operations executed in decision phase
            return jsonify({
                "message": "File uploaded successfully using 2PC",
                "transaction_id": result['transaction_id'],
                "filename": filename,
                "path": metadata["path"]
            }), 201
        else:
            return jsonify({
                "error": "2PC transaction failed",
                "message": result['message'],
                "transaction_id": result['transaction_id']
            }), 500
            
    except ImportError as e:
        # Fallback to original behavior if 2PC not available
        logger.warning(f"2PC not available: {e}, using original upload")
        file.seek(0)
        files = {'file': (filename, file.stream, file.mimetype)}
        resp = requests.post(f"{STORAGE_API}/upload", files=files)
        if resp.status_code != 200:
            return jsonify({"error": "Storage error"}), 500
        try:
            return resp.json(), resp.status_code
        except Exception:
            return jsonify({"error": "Non-JSON response from storage", "raw": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

# list files endpoint
@app.route("/files", methods=["GET"])
@require_auth
def list_files():
    # forward request to metadata service via GET
    resp = requests.get(f"{METADATA_API}/files")

    # check response from metadata service
    if resp.status_code == 200:
        return resp.json(), resp.status_code
    else:
        return jsonify({"error": "Metadata error - " + resp.text}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)