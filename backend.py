from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
import requests
import os
import secrets
import time
from urllib.parse import urlencode

app = Flask(__name__)

CORS(
    app,
    origins=["https://blurryface2011.github.io"],
    allow_headers=["Content-Type", "Authorization"]
)

# ==================================================
# CONFIGURATION
# ==================================================

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

DISCORD_API = "https://discord.com/api/v10"

GITHUB_PAGES = (
    "https://blurryface2011.github.io/"
    "Spam_bot_Dashboard/"
)

# Sessions temporaires
SESSIONS = {}

SESSION_DURATION = 3600  # 1 heure


# ==================================================
# OUTILS
# ==================================================

def bot_headers():
    return {
        "Authorization": f"Bot {BOT_TOKEN}"
    }


def get_session():
    auth = request.headers.get("Authorization", "")

    if not auth.startswith("Bearer "):
        return None

    token = auth[7:]
    session = SESSIONS.get(token)

    if not session:
        return None

    if session["expires"] < time.time():
        del SESSIONS[token]
        return None

    return session


def user_has_guild(session, guild_id):
    return any(
        guild["id"] == str(guild_id)
        for guild in session["guilds"]
    )


# ==================================================
# ROUTES DE BASE
# ==================================================

@app.route("/")
def home():
    return "Backend Discord Dashboard OK"


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ==================================================
# CONNEXION DISCORD
# ==================================================

@app.route("/login")
def login():

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds"
    }

    return redirect(
        "https://discord.com/oauth2/authorize?"
        + urlencode(params)
    )


@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "Code Discord manquant.", 400

    return redirect(
        GITHUB_PAGES + "?code=" + code
    )


# ==================================================
# ÉCHANGE DU CODE DISCORD
# ==================================================

@app.route("/api/exchange", methods=["POST"])
def exchange():

    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({
            "error": "code_missing"
        }), 400

    code = data["code"]

    token_response = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        },
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
        timeout=15
    )

    if token_response.status_code != 200:
        return jsonify({
            "error": "discord_token_error",
            "details": token_response.text
        }), 400

    access_token = token_response.json()["access_token"]

    user_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # -----------------------------
    # UTILISATEUR
    # -----------------------------

    user_response = requests.get(
        f"{DISCORD_API}/users/@me",
        headers=user_headers,
        timeout=15
    )

    if user_response.status_code != 200:
        return jsonify({
            "error": "user_error"
        }), 400

    user = user_response.json()

    # -----------------------------
    # SERVEURS DE L'UTILISATEUR
    # -----------------------------

    guilds_response = requests.get(
        f"{DISCORD_API}/users/@me/guilds",
        headers=user_headers,
        timeout=15
    )

    if guilds_response.status_code != 200:
        return jsonify({
            "error": "guilds_error"
        }), 400

    user_guilds = guilds_response.json()

    # -----------------------------
    # SERVEURS OÙ LE BOT EST PRÉSENT
    # -----------------------------

    bot_guilds = []

    for guild in user_guilds:

        guild_id = guild["id"]

        check = requests.get(
            f"{DISCORD_API}/guilds/{guild_id}",
            headers=bot_headers(),
            timeout=10
        )

        if check.status_code == 200:

            bot_guilds.append({
                "id": guild["id"],
                "name": guild["name"],
                "icon": guild.get("icon"),
                "owner": guild.get("owner"),
                "permissions": guild.get("permissions")
            })

    # -----------------------------
    # CRÉATION SESSION
    # -----------------------------

    session_token = secrets.token_urlsafe(32)

    SESSIONS[session_token] = {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "global_name": user.get("global_name"),
            "avatar": user.get("avatar")
        },
        "guilds": bot_guilds,
        "expires": time.time() + SESSION_DURATION
    }

    return jsonify({
        "session": session_token,
        "user": SESSIONS[session_token]["user"],
        "guilds": bot_guilds
    })


# ==================================================
# SERVEURS
# ==================================================

@app.route("/api/guilds", methods=["GET"])
def get_guilds():

    session = get_session()

    if not session:
        return jsonify({
            "error": "unauthorized"
        }), 401

    return jsonify({
        "guilds": session["guilds"]
    })


# ==================================================
# SALONS D'UN SERVEUR
# ==================================================

@app.route("/api/guilds/<guild_id>/channels", methods=["GET"])
def get_channels(guild_id):

    session = get_session()

    if not session:
        return jsonify({
            "error": "unauthorized"
        }), 401

    if not user_has_guild(session, guild_id):
        return jsonify({
            "error": "guild_not_allowed"
        }), 403

    response = requests.get(
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        headers=bot_headers(),
        timeout=15
    )

    if response.status_code != 200:
        return jsonify({
            "error": "channels_error",
            "details": response.text
        }), response.status_code

    channels = response.json()

    # On garde uniquement les salons textuels classiques
    text_channels = []

    for channel in channels:

        # 0 = text channel
        # 5 = announcement channel
        if channel.get("type") in [0, 5]:

            text_channels.append({
                "id": channel["id"],
                "name": channel["name"],
                "type": channel["type"],
                "parent_id": channel.get("parent_id")
            })

    return jsonify({
        "channels": text_channels
    })


# ==================================================
# ENVOI D'UN MESSAGE
# ==================================================

@app.route("/api/guilds/<guild_id>/send-message", methods=["POST"])
def send_message(guild_id):

    session = get_session()

    if not session:
        return jsonify({
            "error": "unauthorized"
        }), 401

    if not user_has_guild(session, guild_id):
        return jsonify({
            "error": "guild_not_allowed"
        }), 403

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "invalid_json"
        }), 400

    channel_id = data.get("channel_id")
    content = data.get("content")

    if not channel_id:
        return jsonify({
            "error": "channel_missing"
        }), 400

    if not content or not content.strip():
        return jsonify({
            "error": "message_empty"
        }), 400

    # Limite Discord
    if len(content) > 2000:
        return jsonify({
            "error": "message_too_long"
        }), 400

    # ----------------------------------------------
    # Vérification du salon
    # ----------------------------------------------

    channels_response = requests.get(
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        headers=bot_headers(),
        timeout=15
    )

    if channels_response.status_code != 200:
        return jsonify({
            "error": "channels_error"
        }), 400

    channels = channels_response.json()

    valid_channel = None

    for channel in channels:

        if (
            channel["id"] == str(channel_id)
            and channel.get("type") in [0, 5]
        ):
            valid_channel = channel
            break

    if valid_channel is None:
        return jsonify({
            "error": "channel_not_found"
        }), 404

    # ----------------------------------------------
    # ENVOI À DISCORD
    # ----------------------------------------------

    send_response = requests.post(
        f"{DISCORD_API}/channels/{channel_id}/messages",
        headers={
            **bot_headers(),
            "Content-Type": "application/json"
        },
        json={
            "content": content
        },
        timeout=15
    )

    if send_response.status_code not in [200, 201]:
        return jsonify({
            "error": "discord_send_error",
            "details": send_response.text
        }), send_response.status_code

    return jsonify({
        "success": True,
        "message": "Message envoyé."
    })


# ==================================================
# DÉCONNEXION
# ==================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    auth = request.headers.get("Authorization", "")

    if auth.startswith("Bearer "):

        token = auth[7:]

        if token in SESSIONS:
            del SESSIONS[token]

    return jsonify({
        "success": True
    })


# ==================================================
# DÉMARRAGE
# ==================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
