# overlay_server.py
from flask import Flask, request, jsonify

app = Flask(__name__)
latest_message = ""  # store the latest message

@app.route("/send", methods=["POST"])
def send_message():
    global latest_message
    data = request.json
    latest_message = data.get("msg", "")
    return jsonify({"status": "ok", "msg": latest_message})

@app.route("/latest", methods=["GET"])
def get_latest():
    return jsonify({"msg": latest_message})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
