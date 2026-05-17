"""
OAuth para Google Search Console (Webmasters API).
Uso: python src/get_token_gsc.py

Tu cuenta vladys.z96 ya tiene acceso a todas las webs. Solo necesita scope webmasters.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from google_auth_oauthlib.flow import InstalledAppFlow
import socketserver
import wsgiref.simple_server
socketserver.TCPServer.allow_reuse_address = True
wsgiref.simple_server.WSGIServer.allow_reuse_address = True

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Falta YOUTUBE_CLIENT_ID o YOUTUBE_CLIENT_SECRET en .env")
    sys.exit(1)

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
        "https://www.googleapis.com/auth/webmasters",
        "https://www.googleapis.com/auth/webmasters.readonly",
    ],
)

print("\n=== AUTORIZANDO Search Console ===")
print("Loguéate con: vladys.z96@gmail.com (cuenta dueña de las webs)\n")

creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

print("\n=== REFRESH TOKEN ===")
print(creds.refresh_token)

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
key = "GSC_REFRESH_TOKEN"
new_line = f"{key}={creds.refresh_token}\n"
with open(env_path) as f:
    lines = f.readlines()
found = False
for i, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[i] = new_line
        found = True
        break
if not found:
    lines.append(new_line)
with open(env_path, "w") as f:
    f.writelines(lines)
print(f"\n.env actualizado: {key}")
