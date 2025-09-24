import os
import requests
import base64
import json
import string
import random

GITHUB_USER = "669053713850403197963270290945742252531"
GITHUB_REPO = "Celestial"
GITHUB_BRANCH = "main"
GITHUB_FILE = "Users.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # must be set on your system

def generate_key(min_length=25, max_length=40):
    chars = string.ascii_letters + string.digits
    length = random.randint(min_length, max_length)
    return ''.join(random.choices(chars, k=length))

def fetch_whitelist():
    """
    Fetch Users.json from GitHub using personal access token from environment variables.
    Expects the following environment variables to be set on your system:
      - GITHUB_TOKEN
    Returns a list of users (JSON).
    """
    token = os.environ.get("GITHUB_TOKEN")

    if not all([token]):
        raise EnvironmentError("Missing one or more required GitHub environment variables")

    url = f"https://raw.githubusercontent.com/669053713850403197963270290945742252531/Celestial/main/Users.json"
    headers = {
        "Authorization": f"token {token}"
    }

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def update_whitelist(data):
    """Overwrite the Users.json file via GitHub API"""
    import base64
    import json

    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Get current file SHA
    r = requests.get(url + f"?ref={GITHUB_BRANCH}", headers=headers)
    r.raise_for_status()
    sha = r.json()["sha"]

    payload = {
        "message": "Update whitelist via dashboard",
        "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode(),
        "branch": GITHUB_BRANCH,
        "sha": sha
    }
    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()

def get_github_headers():
    token = os.environ.get("GITHUB_TOKEN")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

def fetch_users_from_github():
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}?ref={GITHUB_BRANCH}"
    res = requests.get(url, headers=get_github_headers())
    res.raise_for_status()
    data = res.json()
    content = base64.b64decode(data['content']).decode()
    sha = data['sha']
    return json.loads(content), sha

def update_users_on_github(users, sha):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    payload = {
        "message": "Add new whitelist user",
        "content": base64.b64encode(json.dumps(users, indent=4).encode()).decode(),
        "sha": sha,
        "branch": GITHUB_BRANCH
    }
    res = requests.put(url, headers=get_github_headers(), json=payload)
    res.raise_for_status()
    return res.json()