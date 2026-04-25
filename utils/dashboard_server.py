# utils/dashboard_server.py
# FlowMind – Flask REST API Server
# Serves real-time system state to the dashboard HTML

import threading
from flask import Flask, jsonify
from flask_cors import CORS
from utils.event_store import store

app = Flask(__name__)
CORS(app)


# ── API Endpoints ─────────────────────────────────────────────────────

@app.route("/api/snapshot")
def snapshot():
    """
    Main endpoint — returns full system state.
    Dashboard polls this every second.
    """
    return jsonify(store.get_snapshot())


@app.route("/api/agents")
def agents():
    """Agent status only."""
    with store._lock:
        return jsonify(store.agent_status)


@app.route("/api/incidents")
def incidents():
    """Incident log only."""
    with store._lock:
        return jsonify(store.incidents)


@app.route("/api/kpis")
def kpis():
    """KPI counters only."""
    with store._lock:
        return jsonify(store.kpis)


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status":  "ok",
        "service": "FlowMind Dashboard API",
        "version": "1.0.0",
    })


# ── Server Runner ─────────────────────────────────────────────────────

def run_dashboard_server(port: int = 5000):
    """
    Start Flask server in a background thread.
    Called from main.py before agents start.
    """
    print(f"[Dashboard] 🌐 Starting dashboard server "
          f"on http://localhost:{port}")
    print(f"[Dashboard] 📊 Open dashboard.html in browser")

    thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
    )
    thread.start()
    return thread