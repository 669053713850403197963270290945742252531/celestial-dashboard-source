from flask import Flask, render_template, request, jsonify, session, redirect, Response, url_for
from utils import fetch_whitelist, update_whitelist, fetch_users_from_github, update_users_on_github, generate_key
from datetime import datetime, timedelta
import config
import re
import os
import sqlite3
import subprocess
import hashlib
from functools import wraps
import platform
import uuid

app = Flask(__name__)

# ==========================================================
# Configuration
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
app.secret_key = "celestial_secret_key"

# Session lasts 1 week
app.permanent_session_lifetime = timedelta(weeks=1)
    
# ==========================================================
# Database Setup
# ==========================================================
def init_db():
    print("======================================")
    print("🗄️  Initializing local database")
    print("Using database at:", DB_PATH)
    print("File exists:", os.path.exists(DB_PATH))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    ''')
    conn.commit()

    cursor.execute("SELECT id, username, password FROM users;")
    rows = cursor.fetchall()
    if rows:
        print("\n📋 Current users in database:")
        for row in rows:
            print(f" - ID: {row[0]}, Username: {row[1]}, Password: {row[2][:10]}...")
    else:
        print("\n(no users found yet)")
    print("======================================\n")
    conn.close()

init_db()

# ==========================================================
# Authentication Helpers
# ==========================================================
def login_required(f):
    """Decorator that redirects to login if not signed in."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapper

# ==========================================================
# Flask Globals
# ==========================================================
@app.context_processor
def inject_globals():
    return {
        "site_icon": config.SITE_ICON,
        "site_title": config.SITE_TITLE
    }

# ==========================================================
# Routes
# ==========================================================

@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/users")
@login_required
def users_page():
    return render_template("users.html")

@app.route("/wlmanagement")
@login_required
def wlmanagement():
    users = fetch_whitelist()
    return render_template("whitelist.html", users=users)

# ==========================================================
# API ROUTES
# ==========================================================
@app.route("/api/whitelist", methods=["GET"])
def api_whitelist():
    try:
        users, _ = fetch_users_from_github()
        return jsonify(success=True, users=users)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route("/api/add_user", methods=["POST"])
def add_user():
    try:
        new_user = request.get_json()

        # Fetch current users from GitHub
        users, sha = fetch_users_from_github()

        # Duplicate checks with detailed messages
        dupe_errors = []

        identifier = new_user["Identifier"]
        hwid = new_user["HWID"]
        discord_id = new_user["DiscordId"]

        if not (3 <= len(identifier) <= 20):
            return jsonify(success=False, error="Identifier must be 3-20 characters")
        if len(hwid) != 64:
            return jsonify(success=False, error="HWID must be 64 characters (SHA-256)")
        if not re.fullmatch(r"\d{17,20}", discord_id):
            return jsonify(success=False, error="Discord ID must be 17-20 digits")

        for u in users:
            if u["Identifier"].lower() == new_user["Identifier"].lower():
                dupe_errors.append(f'Identifier already used by "{u["Identifier"]}" (Discord: {u["DiscordId"]})')
            if u["HWID"].lower() == new_user["HWID"].lower():
                dupe_errors.append(f'HWID already used by "{u["Identifier"]}" (Discord: {u["DiscordId"]})')
            if u["DiscordId"] == new_user["DiscordId"]:
                dupe_errors.append(f'Discord ID already used by "{u["Identifier"]}" (HWID: {u["HWID"]})')

        if dupe_errors:
            return jsonify({"success": False, "error": "\n".join(dupe_errors)})

        # Auto-generate Key and ensure uniqueness
        existing_keys = {u["Key"] for u in users}
        key = generate_key()
        while key in existing_keys:
            key = generate_key()
        new_user["Key"] = key

        # Set optional fields
        new_user["Notes"] = new_user.get("Notes", "")
        new_user["JoinDate"] = new_user.get("JoinDate") or datetime.now().strftime("%m/%d/%y %#I:%M:%S %p")

        users.append(new_user)
        update_users_on_github(users, sha)

        return jsonify({"success": True, "user": new_user})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/edit_user", methods=["POST"])
def api_edit_user():
    try:
        data = request.json
        identifier = data["identifier"]  # match frontend
        new_user = data["user"]

        users, sha = fetch_users_from_github()

        # Find user by Identifier
        index = next((i for i, u in enumerate(users) if u["Identifier"] == identifier), None)
        if index is None:
            return jsonify(success=False, error="User not found")

        users[index] = new_user
        update_users_on_github(users, sha)
        return jsonify(success=True, user=new_user)
    except Exception as e:
        return jsonify(success=False, error=str(e))
    
@app.route("/api/remove_user", methods=["POST"])
def remove_user():
    try:
        data = request.get_json()
        identifier = data.get("identifier")
        if not identifier:
            return jsonify({"success": False, "error": "Missing identifier"}), 400

        users, sha = fetch_users_from_github()

        # Find user by Identifier
        index = next((i for i, u in enumerate(users) if u["Identifier"] == identifier), None)
        if index is None:
            return jsonify({"success": False, "error": "User not found"}), 404

        users.pop(index)
        update_users_on_github(users, sha)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
@app.route("/api/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify(success=False, error="Missing credentials")

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password_hash))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify(success=False, error="Invalid username or password")

        # ✅ Login success — set session cookie for a week
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True

        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))
    
@app.route("/api/user_count")
def get_user_count():
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")  # assumes your table is named 'users'
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify(success=True, count=count)
    except Exception as e:
        return jsonify(success=False, error=str(e))
    
# ==========================================================
# MAIN ENTRY
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)