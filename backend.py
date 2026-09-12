from flask import Flask, redirect, request, session, jsonify
from flask_cors import CORS
import requests
import os
import secrets

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

CORS(
    app,
    supports_credentials=True,
    origins=["https://gactcompany.github.io"]
)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI")

DISCORD_API = "https://discord.com/api"


@app.route("/")
def home():
    return "Backend Discord Dashboard OK"


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/login")
def login():
    discord_url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        "&scope=identify%20guilds"
        f"&redirect_uri={REDIRECT_URI}"
    )

    return redirect(discord_url)


@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "Erreur : aucun code Discord reçu.", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    token_response = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data=data,
        headers=headers
    )

    if token_response.status_code != 200:
        return "Erreur lors de la connexion à Discord.", 400

    token_data = token_response.json()

    session["access_token"] = token_data["access_token"]

    return redirect(
        "https://gactcompany.github.io/discord-bot-dashboard/"
    )


@app.route("/api/user")
def get_user():

    access_token = session.get("access_token")

    if not access_token:
        return jsonify({"logged_in": False})

    response = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    if response.status_code != 200:
        return jsonify({"logged_in": False})

    user = response.json()

    return jsonify({
        "logged_in": True,
        "id": user["id"],
        "username": user["username"],
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar")
    })


@app.route("/api/guilds")
def get_guilds():

    access_token = session.get("access_token")

    if not access_token:
        return jsonify({
            "error": "not_logged_in"
        }), 401

    response = requests.get(
        f"{DISCORD_API}/users/@me/guilds",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    if response.status_code != 200:
        return jsonify({
            "error": "discord_error"
        }), response.status_code

    return jsonify(response.json())


@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        "https://gactcompany.github.io/discord-bot-dashboard/"
    )


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
