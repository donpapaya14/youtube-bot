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
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
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
        metrics="views,impressions,impressionClickThroughRate,averageViewPercentage,subscribersGained,subscribersLost,estimatedMinutesWatched",
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
        metrics="views,impressions,impressionClickThroughRate,averageViewPercentage",
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

    total_views = sum(r[1] for r in rows)
    total_impressions = sum(r[2] for r in rows)
    avg_ctr = sum(r[3] for r in rows) / len(rows) if rows else 0
    avg_retention = sum(r[4] for r in rows) / len(rows) if rows else 0
    subs_gained = sum(r[5] for r in rows)

    issues = []
    if total_impressions == 0:
        issues.append("SHADOWBAN_TOTAL: 0 impresiones")
    elif total_impressions < 100:
        issues.append(f"IMPRESIONES_BAJAS: {total_impressions} en {len(rows)}d")
    if avg_ctr < 2:
        issues.append(f"CTR_BAJO: {avg_ctr:.2f}% (objetivo >4%)")
    if avg_retention < 25:
        issues.append(f"RETENCION_BAJA: {avg_retention:.1f}% (objetivo >40%)")
    if subs_gained < 5:
        issues.append(f"GROWTH_DEAD: +{subs_gained} subs en {len(rows)}d")

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
                total_impressions = sum(r[2] for r in rows)
                avg_ctr = sum(r[3] for r in rows) / len(rows)
                avg_ret = sum(r[4] for r in rows) / len(rows)
                gained = sum(r[5] for r in rows)
                lost = sum(r[6] for r in rows)
                print(f"{args.days}d: {total_views} views, {total_impressions} impressions, CTR {avg_ctr:.2f}%, ret {avg_ret:.1f}%, subs +{gained}/-{lost}")
            else:
                print(f"{args.days}d: NO DATA")
            if issues:
                print("ISSUES: " + " | ".join(issues))

            print("TOP 5 VIDEOS:")
            for tr in top.get("rows", [])[:5]:
                vid, views, imp, ctr, ret = tr[0], tr[1], tr[2], tr[3], tr[4]
                print(f"  {vid}: {views}v {imp}imp CTR {ctr:.2f}% ret {ret:.1f}%")

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
