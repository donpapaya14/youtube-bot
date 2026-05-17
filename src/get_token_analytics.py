"""
Genera refresh token OAuth para YouTube + Analytics (2 scopes).
Uso: python src/get_token_analytics.py CANAL_NAME

Re-autoriza con scope yt-analytics.readonly añadido para poder pull metricas.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Falta YOUTUBE_CLIENT_ID o YOUTUBE_CLIENT_SECRET en .env")
    sys.exit(1)

channel_name = sys.argv[1] if len(sys.argv) > 1 else "CHANNEL"

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8080"],
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    scopes=[
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
    ],
)

print(f"\n=== AUTORIZANDO CANAL: {channel_name} ===")
print("Se abrirá navegador. Loguéate con la cuenta Google del canal.\n")

creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

print("\n=== REFRESH TOKEN ===")
print(creds.refresh_token)
print("====================")
print(f"\nGuarda como secret en GitHub:")
print(f"  gh secret set YT_TOKEN_{channel_name.upper()} --repo donpapaya14/youtube-bot")
print(f"\nY en .env local:")
print(f"  YT_TOKEN_{channel_name.upper()}={creds.refresh_token}")
