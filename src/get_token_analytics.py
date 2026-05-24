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
import socketserver
import wsgiref.simple_server
# Permite reusar puerto 8080 entre runs consecutivos (evita "Address already in use")
socketserver.TCPServer.allow_reuse_address = True
wsgiref.simple_server.WSGIServer.allow_reuse_address = True

channel_name = sys.argv[1] if len(sys.argv) > 1 else "CHANNEL"
# Multi-project: 2do arg = project (default, papi, cashcafe)
project = sys.argv[2] if len(sys.argv) > 2 else "default"

if project == "default":
    CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
else:
    CLIENT_ID = os.getenv(f"YOUTUBE_{project.upper()}_CLIENT_ID")
    CLIENT_SECRET = os.getenv(f"YOUTUBE_{project.upper()}_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print(f"ERROR: Falta CLIENT_ID/SECRET para project={project}")
    sys.exit(1)
print(f"Usando project: {project} | client: {CLIENT_ID[:30]}...")

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

# Auto-update .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
key = f"YT_TOKEN_{channel_name.upper()}"
new_line = f"{key}={creds.refresh_token}\n"

if os.path.exists(env_path):
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
else:
    with open(env_path, "w") as f:
        f.write(new_line)
    print(f"\n.env creado: {key}")

print(f"\nAhora actualiza GitHub Secret:")
print(f"  gh secret set {key} --repo donpapaya14/youtube-bot --body '{creds.refresh_token}'")
