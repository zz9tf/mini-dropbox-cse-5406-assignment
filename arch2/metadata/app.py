from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory metadata store
FILES = {}
USERS = {}

# ---------------- Add / Upload Metadata ----------------
@app.route("/files", methods=["POST"])
def add_file():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Store metadata including password
    FILES[filename] = {
        "filename": filename,
        "path": data.get("path"),
        "size": data.get("size"),
        "version": data.get("version", 1),
        "user": data.get("user"),
        "password": data.get("password", "")
    }

    return jsonify(FILES[filename]), 201


# ---------------- Get Metadata ----------------
@app.route("/files/<filename>", methods=["GET"])
def get_file(filename):
    if filename not in FILES:
        return jsonify({"error": "File not found"}), 404
    return jsonify(FILES[filename])


# ---------------- Delete Metadata ----------------
@app.route("/files/<filename>", methods=["DELETE"])
def delete_file(filename):
    if filename not in FILES:
        return jsonify({"error": "File not found"}), 404

    del FILES[filename]
    return jsonify({"status": "deleted"}), 200


# ---------------- List All Files (Optional) ----------------
@app.route("/files", methods=["GET"])
def list_files():
    return jsonify(list(FILES.values())), 200

# ---------------- User Registration ----------------
@app.route("/users", methods=["POST"])
def add_user():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")  # This should be a hashed password
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    if username in USERS:
        return jsonify({"error": "Username already exists"}), 409

    USERS[username] = password
    return jsonify({"message": "User created"}), 201

# ---------------- Get User for Login ----------------
@app.route("/users/<username>", methods=["GET"])
def get_user(username):
    if username not in USERS:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "username": username,
        "password": USERS[username]
    }), 200
# ---------------- Main ---------------- 
if __name__ == "__main__":
    import sys
    import threading
    sys.stdout.reconfigure(line_buffering=True)  # flush prints immediately
    
    # Start 2PC participant server in background thread
    try:
        sys.path.insert(0, '/app')
        sys.path.insert(0, '/app/..')
        from twopc_participant import serve
        
        def start_2pc():
            server = serve(FILES)  # Pass FILES dict reference
            import time
            while True:
                time.sleep(1)
        
        twopc_thread = threading.Thread(target=start_2pc, daemon=True)
        twopc_thread.start()
        print("2PC participant server started on port 6002")
    except ImportError as e:
        print(f"2PC participant not available: {e}")
    
    app.run(host="0.0.0.0", port=5005, debug=True)
