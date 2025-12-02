from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_socketio import SocketIO, emit
import uuid
import json
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Enable WebSocket
latest_message = ""
users_file = "users.json"
sessions = {}  # token: username
admin_logged_in_tokens = set()

# ==========================
# Load and save users
# ==========================
def load_users():
    if os.path.exists(users_file):
        with open(users_file, "r") as f:
            return json.load(f)
    return {}

def save_users():
    with open(users_file, "w") as f:
        json.dump(users, f, indent=4)

users = load_users()

# ==========================
# Overlay Endpoints
# ==========================
@app.route("/", methods=["GET"])
def index():
    return "<h2>Overlay Server Running!</h2><p>Use /latest, /login, /send</p>"

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if username in users and users[username]["password"] == password:
        token = str(uuid.uuid4())
        sessions[token] = username
        return jsonify({"status": "ok", "token": token, "role": users[username]["role"]})
    return jsonify({"status": "fail"}), 401

@app.route("/send", methods=["POST"])
def send_message():
    global latest_message
    data = request.json
    token = data.get("token")
    msg = data.get("msg")
    if not token or token not in sessions:
        return jsonify({"error": "Unauthorized"}), 401
    username = sessions[token]
    if not users[username].get("can_message", False):
        return jsonify({"error": "You are not allowed to send messages"}), 403
    latest_message = msg
    socketio.emit("new_message", {"msg": latest_message})
    return jsonify({"status": "ok", "msg": latest_message})

@app.route("/latest", methods=["GET"])
def get_latest():
    return jsonify({"msg": latest_message})

# ==========================
# Admin Dashboard HTML
# ==========================
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Dashboard</title>
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f8; margin: 0; padding: 0; }
    .container { max-width: 800px; margin: 50px auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);}
    h2 { text-align: center; color: #333; }
    form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
    input, button { padding: 10px; font-size: 16px; border-radius: 4px; border: 1px solid #ccc; }
    button { cursor: pointer; background-color: #007BFF; color: white; border: none; transition: background 0.3s; }
    button:hover { background-color: #0056b3; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
    th { background-color: #007BFF; color: white; }
    a { text-decoration: none; color: #007BFF; }
    a:hover { text-decoration: underline; }
    .error { color: red; text-align: center; margin-bottom: 10px; }
    @media(max-width:600px){ table, th, td { font-size: 14px; } input, button { font-size: 14px; } }
</style>
</head>
<body>
<div class="container">
<h2>Admin Dashboard</h2>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if not logged_in %}
<form method="post" action="/admin">
    <input type="text" name="username" placeholder="Username" required>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
</form>
{% else %}
<h3>Add New User</h3>
<form method="post" action="/add_user">
    <input type="text" name="new_username" placeholder="Username" required>
    <input type="password" name="new_password" placeholder="Password" required>
    <button type="submit">Add User</button>
</form>
<h3>Users</h3>
<table>
<tr><th>Username</th><th>Role</th><th>Can Message</th><th>Actions</th></tr>
{% for u, info in users.items() %}
<tr>
<td>{{ u }}</td>
<td>{{ info.role }}</td>
<td>{{ info.can_message }}</td>
<td>
{% if info.role != 'admin' %}
<a href="/toggle_access?username={{ u }}">Toggle Access</a> | 
<a href="/delete_user?username={{ u }}">Delete</a>
{% else %}-{% endif %}
</td>
</tr>
{% endfor %}
</table>
{% endif %}
</div>
</body>
</html>
"""

@app.route("/admin", methods=["GET", "POST"])
def admin_console():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in users and users[username]["password"] == password and users[username]["role"] == "admin":
            token = str(uuid.uuid4())
            admin_logged_in_tokens.add(token)
            resp = redirect(url_for("admin_console"))
            resp.set_cookie("admin_token", token)
            return resp
        else:
            error = "Invalid credentials"
    token = request.cookies.get("admin_token")
    logged_in = token in admin_logged_in_tokens
    return render_template_string(ADMIN_TEMPLATE, logged_in=logged_in, users=users, error=error)

@app.route("/add_user", methods=["POST"])
def add_user():
    token = request.cookies.get("admin_token")
    if token not in admin_logged_in_tokens:
        return "Unauthorized", 401
    new_username = request.form.get("new_username")
    new_password = request.form.get("new_password")
    if new_username and new_password:
        users[new_username] = {"password": new_password, "role": "user", "can_message": False}
        save_users()
    return redirect(url_for("admin_console"))

@app.route("/toggle_access")
def toggle_access():
    token = request.cookies.get("admin_token")
    if token not in admin_logged_in_tokens:
        return "Unauthorized", 401
    username = request.args.get("username")
    if username in users and users[username]["role"] != "admin":
        users[username]["can_message"] = not users[username]["can_message"]
        save_users()
        socketio.emit("access_changed", {"username": username, "can_message": users[username]["can_message"]})
    return redirect(url_for("admin_console"))

@app.route("/delete_user")
def delete_user():
    token = request.cookies.get("admin_token")
    if token not in admin_logged_in_tokens:
        return "Unauthorized", 401
    username = request.args.get("username")
    if username in users and users[username]["role"] != "admin":
        del users[username]
        save_users()
    return redirect(url_for("admin_console"))

# ==========================
# Run Server
# ==========================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
