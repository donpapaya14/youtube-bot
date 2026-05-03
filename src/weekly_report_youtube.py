"""
Reporte semanal de YouTube — 8 canales.
Envía resumen por Telegram: subs, views, crecimiento, mejor/peor canal.

Uso: python src/weekly_report_youtube.py
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from publisher import notify_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("weekly_report")

# Todos los canales con sus tokens
CHANNELS = [
    {"name": "VidaSana360", "token_env": "YT_TOKEN_PRINCIPAL"},
    {"name": "SaludLongevidad", "token_env": "YT_TOKEN_SALUD"},
    {"name": "FinanzasClara", "token_env": "YT_TOKEN_FINANZAS"},
    {"name": "CatBrothers", "token_env": "YT_TOKEN_CATBROTHERS"},
    {"name": "HogarInteligente", "token_env": "YT_TOKEN_HOGARINTELIGENTE"},
    {"name": "ChillOrbit", "token_env": "YT_TOKEN_DARKFILES"},
    {"name": "CalmEarth", "token_env": "YT_TOKEN_CALMEARTH"},
    {"name": "DarkFiles", "token_env": "YT_TOKEN_CHILLORBIT"},
]


def get_channel_stats(token_env: str) -> dict | None:
    """Obtiene estadísticas del canal."""
    refresh_token = os.getenv(token_env)
    if not refresh_token:
        return None

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YOUTUBE_CLIENT_ID"),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        )
        youtube = build("youtube", "v3", credentials=creds)

        # Stats del canal
        ch = youtube.channels().list(part="statistics,snippet", mine=True).execute()
        if not ch.get("items"):
            return None

        item = ch["items"][0]
        stats = item["statistics"]

        # Videos recientes (última semana)
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
        search = youtube.search().list(
            part="id",
            forMine=True,
            type="video",
            publishedAfter=week_ago,
            maxResults=50,
        ).execute()
        videos_this_week = search.get("pageInfo", {}).get("totalResults", 0)

        # Top video de la semana (por views)
        top_video = None
        if search.get("items"):
            video_ids = [v["id"]["videoId"] for v in search["items"][:10]]
            vids = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(video_ids),
            ).execute()

            best = None
            for v in vids.get("items", []):
                views = int(v["statistics"].get("viewCount", 0))
                if not best or views > best["views"]:
                    best = {
                        "title": v["snippet"]["title"][:50],
                        "views": views,
                        "id": v["id"],
                    }
            top_video = best

        return {
            "channel_name": item["snippet"]["title"],
            "subscribers": int(stats.get("subscriberCount", 0)),
            "total_views": int(stats.get("viewCount", 0)),
            "total_videos": int(stats.get("videoCount", 0)),
            "videos_this_week": videos_this_week,
            "top_video": top_video,
        }

    except Exception as e:
        log.error("Error obteniendo stats: %s", str(e)[:100])
        return None


def format_number(n: int) -> str:
    """Formatea número: 1234 → 1.2K"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def main():
    log.info("Generando reporte semanal YouTube...")
    results = []

    for ch in CHANNELS:
        log.info("Consultando %s...", ch["name"])
        stats = get_channel_stats(ch["token_env"])
        if stats:
            stats["config_name"] = ch["name"]
            results.append(stats)
            log.info("  %s: %d subs, %d views", ch["name"], stats["subscribers"], stats["total_views"])
        else:
            log.warning("  %s: sin datos", ch["name"])

    if not results:
        notify_telegram("❌ <b>Reporte YouTube</b>\n\nNo se pudieron obtener datos de ningún canal.")
        return

    # Ordenar por suscriptores
    results.sort(key=lambda x: x["subscribers"], reverse=True)

    # Construir mensaje
    date_str = datetime.utcnow().strftime("%d/%m/%Y")
    lines = [f"📊 <b>Reporte YouTube Semanal</b> — {date_str}\n"]

    # Shorts channels
    shorts = [r for r in results if r["config_name"] in ("VidaSana360", "SaludLongevidad", "FinanzasClara", "CatBrothers", "HogarInteligente")]
    longform = [r for r in results if r["config_name"] in ("ChillOrbit", "CalmEarth", "DarkFiles")]

    if shorts:
        lines.append("📱 <b>SHORTS</b>")
        for r in shorts:
            top = ""
            if r.get("top_video"):
                top = f"\n   🏆 {r['top_video']['title']} ({format_number(r['top_video']['views'])} views)"
            lines.append(
                f"  <b>{r['config_name']}</b>\n"
                f"   👥 {format_number(r['subscribers'])} subs | "
                f"👁 {format_number(r['total_views'])} views\n"
                f"   📹 {r['videos_this_week']} videos esta semana"
                f"{top}"
            )
        lines.append("")

    if longform:
        lines.append("🎬 <b>LONG-FORM</b>")
        for r in longform:
            top = ""
            if r.get("top_video"):
                top = f"\n   🏆 {r['top_video']['title']} ({format_number(r['top_video']['views'])} views)"
            lines.append(
                f"  <b>{r['config_name']}</b>\n"
                f"   👥 {format_number(r['subscribers'])} subs | "
                f"👁 {format_number(r['total_views'])} views\n"
                f"   📹 {r['videos_this_week']} videos esta semana"
                f"{top}"
            )
        lines.append("")

    # Resumen
    total_subs = sum(r["subscribers"] for r in results)
    total_views = sum(r["total_views"] for r in results)
    total_vids_week = sum(r["videos_this_week"] for r in results)

    best = max(results, key=lambda x: x.get("top_video", {}).get("views", 0) if x.get("top_video") else 0)
    worst = min(results, key=lambda x: x["total_views"])

    lines.append(
        f"📈 <b>RESUMEN</b>\n"
        f"   Total subs: {format_number(total_subs)}\n"
        f"   Total views: {format_number(total_views)}\n"
        f"   Videos esta semana: {total_vids_week}\n"
        f"   🟢 Mejor: {best['config_name']}\n"
        f"   🔴 Peor: {worst['config_name']}"
    )

    msg = "\n".join(lines)
    notify_telegram(msg)
    log.info("Reporte enviado por Telegram")


if __name__ == "__main__":
    main()
