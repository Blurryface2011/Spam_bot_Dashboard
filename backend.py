from flask import Flask
from flask_cors import CORS
import os

app = Flask(__name__)

# Autorise GitHub Pages à communiquer avec Render
CORS(app)

@app.route("/")
def home():
    return "Backend Discord Dashboard OK"

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
