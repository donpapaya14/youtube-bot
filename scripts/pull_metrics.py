"""
Pull YouTube Analytics metrics para todos los canales.
Detecta shadowban: impresiones=0, CTR<2%, retention<25%.

Uso: python scripts/pull_metrics.py [--days 28] [--channel CANAL]
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CID = os.environ["YOUTUBE_CLIENT_ID"]
CSEC = os.environ["YOUTUBE_CLIENT_SECRET"]

CHANNELS = {
    "PRINCIPAL": "VidaSana360",
    "SALUD": "SaludLongevidad",
    "FINANZAS": "FinanzasClara",
    "CATBROTHERS": "CatBrothers",
    "HOGARINTELIGENTE": "EspacioInteligente",
    "CHILLORBIT": "MindWired",
    "DARKFILES": "DarkFiles",
    "CALMEARTH": "DisasterDecode",
    "CASHCAFE": "CashCafe",
    "DONVLADYS": "DonVladys",
}


def yt_clients(refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CID,
        client_secret=CSEC,
        scopes=[
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
            "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
        ],
    )
    yt = build("youtube", "v3", credentials=creds)
    yta = build("youtubeAnalytics", "v2", credentials=creds)
    return yt, yta


def get_channel_id(yt) -> str:
    r = yt.channels().list(part="id,snippet,statistics", mine=True).execute()
    return r["items"][0]


def pull_channel_metrics(yta, channel_id: str, days: int = 28) -> dict:
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    r = yta.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,averageViewPercentage,averageViewDuration",
        dimensions="day",
    ).execute()
    return r


def pull_top_videos(yta, channel_id: str, days: int = 28) -> dict:
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    r = yta.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics="views,estimatedMinutesWatched,averageViewPercentage,averageViewDuration",
        dimensions="video",
        sort="-views",
        maxResults=10,
    ).execute()
    return r


def diagnose(channel_data: dict) -> list[str]:
    """Retorna lista de problemas detectados."""
    rows = channel_data.get("rows", [])
    if not rows:
        return ["NO_DATA"]
    # row format: [day, views, watchMinutes, subsGained, subsLost, avgViewPct, avgViewDur]
    total_views = sum(r[1] for r in rows)
    total_watch_min = sum(r[2] for r in rows)
    subs_gained = sum(r[3] for r in rows)
    subs_lost = sum(r[4] for r in rows)
    avg_retention = sum(r[5] for r in rows) / len(rows) if rows else 0
    avg_view_duration = sum(r[6] for r in rows) / len(rows) if rows else 0

    issues = []
    if total_views == 0:
        issues.append("SHADOWBAN_TOTAL: 0 views")
    elif total_views < 50:
        issues.append(f"VIEWS_BAJAS: {total_views} en {len(rows)}d")
    if avg_retention < 25:
        issues.append(f"RETENCION_BAJA: {avg_retention:.1f}% (objetivo >40%)")
    if subs_gained < 5:
        issues.append(f"GROWTH_DEAD: +{subs_gained} subs en {len(rows)}d")
    if subs_lost > subs_gained:
        issues.append(f"NEGATIVE_GROWTH: -{subs_lost} vs +{subs_gained}")

    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--channel", help="Solo un canal (token env name)")
    args = ap.parse_args()

    report = {}
    targets = {args.channel: CHANNELS[args.channel]} if args.channel else CHANNELS

    for env_name, ch_name in targets.items():
        token = os.getenv(f"YT_TOKEN_{env_name}")
        if not token:
            print(f"[SKIP] {ch_name}: sin YT_TOKEN_{env_name}")
            continue
        try:
            yt, yta = yt_clients(token)
            info = get_channel_id(yt)
            ch_id = info["id"]
            stats = info.get("statistics", {})

            metrics = pull_channel_metrics(yta, ch_id, args.days)
            top = pull_top_videos(yta, ch_id, args.days)
            issues = diagnose(metrics)

            print(f"\n=== {ch_name} ({env_name}) ===")
            print(f"Subs totales: {stats.get('subscriberCount','?')} | Views totales: {stats.get('viewCount','?')}")
            rows = metrics.get("rows", [])
            if rows:
                total_views = sum(r[1] for r in rows)
                total_wm = sum(r[2] for r in rows)
                gained = sum(r[3] for r in rows)
                lost = sum(r[4] for r in rows)
                avg_ret = sum(r[5] for r in rows) / len(rows)
                avg_dur = sum(r[6] for r in rows) / len(rows)
                print(f"{args.days}d: {total_views} views, {total_wm} watch_min, subs +{gained}/-{lost}, ret {avg_ret:.1f}%, avg_dur {avg_dur:.1f}s")
            else:
                print(f"{args.days}d: NO DATA")
            if issues:
                print("ISSUES: " + " | ".join(issues))

            print("TOP 5 VIDEOS:")
            for tr in top.get("rows", [])[:5]:
                vid, views, wm, ret, dur = tr[0], tr[1], tr[2], tr[3], tr[4]
                print(f"  {vid}: {views}v {wm}min ret {ret:.1f}% dur {dur:.1f}s")

            report[ch_name] = {
                "subs_total": stats.get("subscriberCount"),
                "views_total": stats.get("viewCount"),
                "metrics_28d": metrics.get("rows", []),
                "top_videos": top.get("rows", []),
                "issues": issues,
            }
        except Exception as e:
            print(f"[ERR] {ch_name}: {str(e)[:200]}")
            report[ch_name] = {"error": str(e)[:200]}

    out = Path(__file__).parent.parent / f"metrics_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n=== Report saved: {out} ===")


if __name__ == "__main__":
    main()
