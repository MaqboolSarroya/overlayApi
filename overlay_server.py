from flask import Flask, request, jsonify
import os

app = Flask(__name__)
latest_message = ""  # store the latest message

@app.route("/", methods=["GET"])
def index():
    return """
    <h2>Overlay Server Running!</h2>
    <p>Use <code>/latest</code> to fetch latest message (GET).</p>
    <p>Use <code>/send</code> to send message (POST JSON {"msg":"your message"}).</p>
    """

@app.route("/send", methods=["POST"])
def send_message():
    global latest_message
    data = request.json
    if not data or "msg" not in data:
        return jsonify({"error": "Missing 'msg' in JSON"}), 400

    latest_message = data["msg"]
    return jsonify({"status": "ok", "msg": latest_message})

@app.route("/latest", methods=["GET"])
def get_latest():
    return jsonify({"msg": latest_message})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
