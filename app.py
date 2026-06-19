from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    Response,
    url_for,
)
from utils import (
    fetch_whitelist,
    update_whitelist,
    fetch_users_from_github,
    update_users_on_github,
    generate_key,
    get_github_headers,
    GITHUB_USER,
    GITHUB_REPO,
    GITHUB_FILE,
    GITHUB_BRANCH,
)
from datetime import datetime, timedelta, timezone
import config
import re
import os
import sqlite3
import subprocess
import hashlib
from functools import wraps
import platform
import uuid
import requests
import base64
import json
import time

app = Flask(__name__, static_folder="resources", static_url_path="/resources")

# ==========================================================
# Configuration, Variables, & Constants
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
app.secret_key = "celestial_secret_key"

# Session lasts 1 week
app.permanent_session_lifetime = timedelta(weeks=1)
start_time = time.time()
SERVER_START_TIMESTAMP = time.time()


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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    """
    )
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
# Helpers
# ==========================================================
FIELD_ORDER = ["Identifier", "HWID", "DiscordId", "Rank", "JoinDate", "Key", "Notes"]

def normalize_user(user):
    return {field: user.get(field) for field in FIELD_ORDER}

def login_required(f):
    """Decorator that redirects to login if not signed in."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)

    return wrapper


def get_user_id(query):
    if query.isdigit():
        return query

    url = "https://users.roblox.com/v1/usernames/users"
    res = requests.post(
        url, json={"usernames": [query], "excludeBannedUsers": False}
    ).json()

    if res["data"]:
        return res["data"][0]["id"]

    return None


def get_avatar(user_id, avatar_type):
    type_map = {"headshot": "avatar-headshot", "bust": "avatar-bust", "full": "avatar"}

    url = f"https://thumbnails.roblox.com/v1/users/{type_map[avatar_type]}?userIds={user_id}&size=150x150&format=Png"
    return requests.get(url).json()["data"][0]["imageUrl"]


# ==========================================================
# Flask Globals
# ==========================================================
@app.context_processor
def inject_globals():
    return {"site_icon": config.SITE_ICON, "site_title": config.SITE_TITLE}


# ==========================================================
# Routes
# ==========================================================


@app.route("/")
def root():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", page_title="Dashboard")


@app.route("/users")
@login_required
def users_page():
    users = fetch_whitelist()
    return render_template("users.html", users=users, page_title="User Management")


@app.route("/whitelist")
@login_required
def whitelist_management():
    return render_template("whitelist.html", page_title="Whitelist Management")


@app.route("/hashing")
@login_required
def hashing_page():
    return render_template("hashing.html", page_title="Hashing")


@app.route("/rbxlookup")
@login_required
def lookup_page():
    return render_template("rbxlookup.html", page_title="Roblox User Lookup")


@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html", page_title="Settings")


# ==========================================================
# TO BE COMPLETED
# ==========================================================


@app.route("/binary-conversion")
@login_required
def binary_translate_page():
    return render_template("binary-conversion.html")


@app.route("/color-conversion")
@login_required
def color_translate_page():
    return render_template("color-conversion.html")


@app.route("/generation")
@login_required
def string_generation_page():
    return render_template("generation.html")


@app.route("/time-conversion")
@login_required
def time_conversion_page():
    return render_template("time-conversion.html")


@app.route("/encoding-decoding")
@login_required
def string_encoding_decoding_page():
    return render_template("encoding-decoding.html")


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
                dupe_errors.append(
                    f'Identifier already used by "{u["Identifier"]}" (Discord: {u["DiscordId"]})'
                )
            if u["HWID"].lower() == new_user["HWID"].lower():
                dupe_errors.append(
                    f'HWID already used by "{u["Identifier"]}" (Discord: {u["DiscordId"]})'
                )
            if u["DiscordId"] == new_user["DiscordId"]:
                dupe_errors.append(
                    f'Discord ID already used by "{u["Identifier"]}" (HWID: {u["HWID"]})'
                )

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
        new_user["JoinDate"] = new_user.get("JoinDate") or datetime.now().strftime(
            "%m/%d/%y %#I:%M:%S %p"
        )

        users.append(normalize_user(new_user))
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
        index = next(
            (i for i, u in enumerate(users) if u["Identifier"] == identifier), None
        )
        if index is None:
            return jsonify(success=False, error="User not found")

        users[index] = normalize_user(new_user)
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
        index = next(
            (i for i, u in enumerate(users) if u["Identifier"] == identifier), None
        )
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
        cursor.execute(
            "SELECT id FROM users WHERE username=? AND password=?",
            (username, password_hash),
        )
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
        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )  # assumes your table is named 'users'
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify(success=True, count=count)
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.route("/api/session_status")
def session_status():
    session_cookie = request.cookies.get("session")
    if session_cookie:
        return jsonify({"status": "valid"})
    else:
        return jsonify({"status": "invalid"})


@app.route("/api/github_users", methods=["GET"])
def api_github_users():
    try:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        res = requests.get(url, headers=get_github_headers())
        res.raise_for_status()
        content = res.json()

        # Decode the GitHub file content correctly
        users = json.loads(base64.b64decode(content["content"]).decode())
        sha = content["sha"]

        # Return only clean data
        return jsonify({"users": users, "sha": sha})
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/github_update_users", methods=["POST"])
def api_github_update_users():
    try:
        data = request.get_json()
        users = data.get("users")
        sha = data.get("sha")

        if not users:
            return jsonify(success=False, error="Missing users"), 400

        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        payload = {
            "message": "Update whitelist data via dashboard",
            "content": base64.b64encode(json.dumps(users, indent=4).encode()).decode(),
            "sha": sha,
            "branch": GITHUB_BRANCH,
        }

        res = requests.put(url, headers=get_github_headers(), json=payload)

        # If 409, fetch latest SHA and retry
        if res.status_code == 409:
            latest = requests.get(
                url, headers=get_github_headers(), params={"ref": GITHUB_BRANCH}
            )
            latest.raise_for_status()
            latest_sha = latest.json()["sha"]

            payload["sha"] = latest_sha
            res = requests.put(url, headers=get_github_headers(), json=payload)

        res.raise_for_status()
        return jsonify(success=True, sha=res.json().get("content", {}).get("sha", ""))

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/uptime")
def uptime():
    return jsonify(
        {
            "success": True,
            "server_start": SERVER_START_TIMESTAMP,  # store this once when app boots
        }
    )


@app.route("/api/reroll_key", methods=["POST"])
def reroll_key():
    try:
        data = request.get_json()
        identifier = data.get("identifier")

        if not identifier:
            return jsonify(success=False, error="Missing identifier"), 400

        # Fetch users + SHA
        users, sha = fetch_users_from_github()

        # Find existing user
        user_index = next(
            (i for i, u in enumerate(users) if u["Identifier"] == identifier), None
        )
        if user_index is None:
            return jsonify(success=False, error="User not found"), 404

        # Generate new unique key
        existing_keys = {u["Key"] for u in users}
        new_key = generate_key()
        while new_key in existing_keys:
            new_key = generate_key()

        # Update the key
        users[user_index]["Key"] = new_key
        users[user_index] = normalize_user(users[user_index])

        # Commit update to GitHub
        update_users_on_github(users, sha)

        return jsonify(success=True, new_key=new_key)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/user")
def get_user():
    query = request.args.get("query")

    user_id = get_user_id(query)
    if not user_id:
        return jsonify({"error": "User not found"})

    user = requests.get(f"https://users.roblox.com/v1/users/{user_id}").json()

    avatar = requests.get(
        f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
    ).json()

    presence = requests.post(
        "https://presence.roblox.com/v1/presence/users",
        json={"userIds": [int(user_id)]},
    ).json()

    p = presence["userPresences"][0]

    return jsonify(
        {
            "id": user_id,
            "username": user["name"],
            "displayName": user["displayName"],
            "description": user["description"],
            "created": user["created"],
            "avatar": avatar["data"][0]["imageUrl"],
            "status": p["userPresenceType"],
            "lastOnline": p.get("lastOnline"),
            "placeId": p.get("placeId"),
            "jobId": p.get("gameId"),
            "joinable": p.get("placeId") and p.get("gameId"),
        }
    )


@app.route("/api/full")
def full():
    query = request.args.get("query")
    avatar_type = request.args.get("avatar", "headshot")

    user_id = get_user_id(query)
    if not user_id:
        return jsonify({"error": "User not found"})

    user = requests.get(f"https://users.roblox.com/v1/users/{user_id}").json()

    # Friends
    friends = (
        requests.get(f"https://friends.roblox.com/v1/users/{user_id}/friends")
        .json()
        .get("data", [])
    )

    # Groups
    groups = (
        requests.get(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles")
        .json()
        .get("data", [])
    )

    # Followers / Following
    followers = requests.get(
        f"https://friends.roblox.com/v1/users/{user_id}/followers/count"
    ).json()
    following = requests.get(
        f"https://friends.roblox.com/v1/users/{user_id}/followings/count"
    ).json()
    friends_count = requests.get(
        f"https://friends.roblox.com/v1/users/{user_id}/friends/count"
    ).json()

    # Inventory (may fail)
    inventory = []

    try:
        assets = requests.get(
            f"https://inventory.roblox.com/v2/users/{user_id}/inventory?assetTypes=Hat,Shirt,Pants,Face,Gear&limit=50"
        ).json()

        inventory = assets.get("data", [])

    except:
        inventory = None

    presence = requests.post(
        "https://presence.roblox.com/v1/presence/users",
        json={"userIds": [int(user_id)]},
    ).json()

    p = presence["userPresences"][0]

    status_map = {0: "Offline", 1: "Online", 2: "In Game", 3: "In Studio"}

    # Presence data
    userPresenceType = p.get("userPresenceType")  # 0=offline, 1=online, 2=in-game

    place_id = p.get("placeId")
    job_id = p.get("gameId")

    # Better logic
    can_join = userPresenceType == 2 and place_id is not None

    # Optional: fallback flag (UI hint)
    if userPresenceType == 2:
        join_status = "in_game"
    else:
        join_status = "not_in_game"

    return jsonify(
        {
            "id": user_id,
            "username": user["name"],
            "displayName": user["displayName"],
            "description": user["description"],
            "created": user["created"],
            "avatar": get_avatar(user_id, avatar_type),
            "friends": friends,
            "groups": [
                {"name": g["group"]["name"], "role": g["role"]["name"]} for g in groups
            ],
            "inventory": (
                [{"name": i["name"], "assetId": i["assetId"]} for i in inventory]
                if inventory
                else None
            ),
            "followers": followers.get("count", 0),
            "following": following.get("count", 0),
            "friendsCount": friends_count.get("count", 0),
            "status": status_map.get(p["userPresenceType"], "Unknown"),
            "lastOnline": p.get("lastOnline"),
            "placeId": place_id,
            "jobId": job_id,
            "canJoin": can_join,
            "joinStatus": join_status,
        }
    )

@app.route("/api/save_all", methods=["POST"])
@login_required
def save_all():
    try:
        data = request.get_json()
        incoming_users = data.get("users")

        if incoming_users is None:
            return jsonify(success=False, error="Missing users array"), 400

        # Fetch current SHA (needed to commit to GitHub)
        users, sha = fetch_users_from_github()

        # Build a set of existing keys for uniqueness checks during reroll
        existing_keys = {u["Key"] for u in users}

        # Process each incoming user
        cleaned = []
        for u in incoming_users:
            user = dict(u)

            pending_reroll = user.pop("_pendingReroll", False)  # capture it
            user.pop("whitelisted", None)

            if pending_reroll:  # use the captured value
                new_key = generate_key()
                while new_key in existing_keys:
                    new_key = generate_key()
                existing_keys.add(new_key)
                user["Key"] = new_key

            if not user.get("Key"):
                new_key = generate_key()
                while new_key in existing_keys:
                    new_key = generate_key()
                existing_keys.add(new_key)
                user["Key"] = new_key

            if not user.get("Notes"):
                user["Notes"] = None

            cleaned.append(normalize_user(user))

        # Commit the full cleaned array to GitHub
        update_users_on_github(cleaned, sha)

        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

# ==========================================================
# MAIN ENTRY
# ==========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
