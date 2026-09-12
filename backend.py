from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
import requests
import os
from urllib.parse import urlencode

app = Flask(__name__)

CORS(app, origins=[
    "https://blurryface2011.github.io"
])

# =========================
# CONFIGURATION
# =========================

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

DISCORD_API = "https://discord.com/api"

GITHUB_PAGES = (
    "https://blurryface2011.github.io/"
    "Spam_bot_Dashboard/"
)


# =========================
# ACCUEIL
# =========================

@app.route("/")
def home():
    return "Backend Discord Dashboard OK"


# =========================
# HEALTH CHECK
# =========================

@app.route("/health")
def health():
    return {"status": "ok"}


# =========================
# CONNEXION DISCORD
# =========================

@app.route("/login")
def login():

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds"
    }

    url = (
        "https://discord.com/oauth2/authorize?"
        + urlencode(params)
    )

    return redirect(url)


# =========================
# CALLBACK DISCORD
# =========================

@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "Code Discord manquant.", 400

    return redirect(
        GITHUB_PAGES + "?code=" + code
    )


# =========================
# ÉCHANGE DU CODE OAUTH
# =========================

@app.route("/api/exchange", methods=["POST"])
def exchange():

    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({
            "error": "code_missing"
        }), 400

    code = data["code"]


    # -------------------------
    # Récupération du token OAuth
    # -------------------------

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
        }
    )


    if token_response.status_code != 200:

        return jsonify({
            "error": "discord_token_error"
        }), 400


    token_data = token_response.json()

    access_token = token_data["access_token"]


    # -------------------------
    # Informations utilisateur
    # -------------------------

    user_response = requests.get(

        f"{DISCORD_API}/users/@me",

        headers={
            "Authorization":
                f"Bearer {access_token}"
        }
    )


    if user_response.status_code != 200:

        return jsonify({
            "error": "user_error"
        }), 400


    user = user_response.json()


    # -------------------------
    # Serveurs de l'utilisateur
    # -------------------------

    user_guilds_response = requests.get(

        f"{DISCORD_API}/users/@me/guilds",

        headers={
            "Authorization":
                f"Bearer {access_token}"
        }
    )


    if user_guilds_response.status_code != 200:

        return jsonify({
            "error": "guilds_error"
        }), 400


    user_guilds = user_guilds_response.json()


    # -------------------------
    # Serveurs du BOT
    # -------------------------

    bot_guilds_response = requests.get(

        f"{DISCORD_API}/users/@me/guilds",

        headers={
            "Authorization":
                f"Bot {BOT_TOKEN}"
        }
    )


    if bot_guilds_response.status_code != 200:

        return jsonify({
            "error": "bot_guilds_error"
        }), 500


    bot_guilds = bot_guilds_response.json()


    # -------------------------
    # IDs des serveurs du BOT
    # -------------------------

    bot_guild_ids = {
        guild["id"]
        for guild in bot_guilds
    }


    # -------------------------
    # Serveurs communs
    # -------------------------

    common_guilds = [

        guild

        for guild in user_guilds

        if guild["id"] in bot_guild_ids

    ]


    # -------------------------
    # Réponse au dashboard
    # -------------------------

    return jsonify({

        "user": {

            "id":
                user["id"],

            "username":
                user["username"],

            "global_name":
                user.get("global_name"),

            "avatar":
                user.get("avatar")

        },

        "guilds":
            common_guilds

    })


# =========================
# LANCEMENT
# =========================

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
