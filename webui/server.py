"""Flask server: serves FreqUI static files and exposes QNT data API."""
import json
import os
import time

from flask import Flask, Response, jsonify, send_from_directory
from flask_cors import CORS

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frequi", "dist")

app = Flask(__name__, static_folder=DIST, static_url_path="")
CORS(app)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    full = os.path.join(app.static_folder, path)
    if os.path.isfile(full):
        return send_from_directory(app.static_folder, path)
    # SPA fallback
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/qnt/oracle")
def oracle():
    score_path = os.path.join(BASE, "sentiment", "scores", "current_score.json")
    try:
        with open(score_path) as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Score file not found", "score": 0, "regime": "NEUTRAL"}), 200
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid score file", "score": 0, "regime": "NEUTRAL"}), 200


@app.route("/api/qnt/shield")
def shield():
    state_path = os.path.join(BASE, "risk", "balance_state.json")
    try:
        with open(state_path) as f:
            state = json.load(f)

        start_of_day = state.get("start_of_day", 0)
        last_balance = state.get("last_seen_balance", start_of_day)
        start_of_week = state.get("start_of_week", start_of_day)

        daily_drawdown = 0.0
        weekly_drawdown = 0.0
        if start_of_day > 0:
            daily_drawdown = ((start_of_day - last_balance) / start_of_day) * 100
        if start_of_week > 0:
            weekly_drawdown = ((start_of_week - last_balance) / start_of_week) * 100

        # Clamp negatives (profit) to 0
        daily_drawdown = max(0.0, daily_drawdown)
        weekly_drawdown = max(0.0, weekly_drawdown)

        return jsonify(
            {
                "status": "PROTECTED" if daily_drawdown < 3.0 else "BREACHED",
                "daily_drawdown": round(daily_drawdown, 2),
                "weekly_drawdown": round(weekly_drawdown, 2),
                "daily_limit": 3.0,
                "weekly_limit": 7.0,
                "last_balance": round(last_balance, 2),
                "last_updated": state.get("last_updated", ""),
            }
        )
    except FileNotFoundError:
        return jsonify({"error": "Balance state not found", "status": "UNKNOWN"}), 200
    except (json.JSONDecodeError, ZeroDivisionError):
        return jsonify({"error": "Could not parse balance state", "status": "UNKNOWN"}), 200


@app.route("/api/qnt/logs")
def logs():
    log_dir = os.path.join(BASE, "logs")

    def generate():
        while True:
            entries = []
            try:
                for fname in sorted(os.listdir(log_dir)):
                    if fname.endswith(".stderr.log") or fname.endswith(".log"):
                        fpath = os.path.join(log_dir, fname)
                        try:
                            with open(fpath) as lf:
                                lines = lf.readlines()[-3:]
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        entries.append(
                                            {"source": fname.replace(".stderr.log", "").replace(".log", ""), "line": line}
                                        )
                        except OSError:
                            continue
            except OSError:
                entries = [{"source": "system", "line": f"Log directory not found: {log_dir}"}]

            yield f"data: {json.dumps(entries)}\n\n"
            time.sleep(5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/qnt/health")
def health():
    return jsonify({"status": "ok", "service": "masterbot-webui"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
