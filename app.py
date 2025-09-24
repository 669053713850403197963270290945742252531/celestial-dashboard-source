from flask import Flask, render_template, request, jsonify
from utils import fetch_whitelist, update_whitelist, fetch_users_from_github, update_users_on_github, generate_key
from datetime import datetime
import config
import re
import os

app = Flask(__name__)

# Inject global site info
@app.context_processor
def inject_globals():
    return {
        "site_icon": config.SITE_ICON,
        "site_title": config.SITE_TITLE
    }

# Routes
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/users")
def users():
    return render_template("users.html")

@app.route("/wlmanagement")
def wlmanagement():
    users = fetch_whitelist()
    return render_template("whitelist.html", users=users)

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
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    app.run(debug=True)