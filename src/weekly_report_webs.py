"""
Reporte semanal de las 5 webs SEO.
Cuenta artículos publicados, verifica que están online, y reporta por Telegram.

Uso: python src/weekly_report_webs.py
"""

import json
import logging
import os
import sys
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

import requests
from publisher import notify_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("weekly_report_webs")

WEBS = [
    {"name": "VidaSana360", "domain": "vida-sana-360.com", "repo": "donpapaya14/vidasana360-web"},
    {"name": "SaludLongevidad", "domain": "saludlongevidad.org", "repo": "donpapaya14/saludlongevidad-web"},
    {"name": "FinanzasClara", "domain": "finanzasclara.uk", "repo": "donpapaya14/finanzasclara-web"},
    {"name": "CatBrothers", "domain": "catbrothers.uk", "repo": "donpapaya14/catbrothers-web"},
    {"name": "EspacioInteligente", "domain": "espaciointeligente.org", "repo": "donpapaya14/hogarinteligente-web"},
]


def check_web(web: dict) -> dict:
    """Verifica estado de una web y cuenta artículos."""
    result = {
        "name": web["name"],
        "domain": web["domain"],
        "online": False,
        "articles_total": 0,
        "articles_this_week": 0,
        "status_code": 0,
        "actions_runs_ok": 0,
        "actions_runs_fail": 0,
    }

    # 1. Check si está online
    try:
        resp = requests.get(f"https://{web['domain']}", timeout=15, allow_redirects=True)
        result["online"] = resp.status_code == 200
        result["status_code"] = resp.status_code
    except Exception as e:
        log.warning("%s offline: %s", web["name"], str(e)[:60])

    # 2. Contar artículos via sitemap
    try:
        sitemap_url = f"https://{web['domain']}/sitemap-0.xml"
        resp = requests.get(sitemap_url, timeout=15)
        if resp.status_code == 200:
            # Contar <url> tags en sitemap
            urls = resp.text.count("<url>")
            # Restar 1 por la home
            result["articles_total"] = max(urls - 1, 0)

            # Contar artículos de esta semana (por lastmod)
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            lines = resp.text.split("\n")
            recent = sum(1 for line in lines if "<lastmod>" in line and line.strip().replace("<lastmod>", "").replace("</lastmod>", "")[:10] >= week_ago)
            result["articles_this_week"] = recent
        else:
            # Intentar sitemap principal
            sitemap_url = f"https://{web['domain']}/sitemap.xml"
            resp = requests.get(sitemap_url, timeout=15)
            if resp.status_code == 200:
                result["articles_total"] = resp.text.count("<url>") - 1
    except Exception as e:
        log.warning("%s sitemap error: %s", web["name"], str(e)[:60])

    # 3. GitHub Actions runs esta semana
    try:
        gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if gh_token:
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
            headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
            api_url = f"https://api.github.com/repos/{web['repo']}/actions/runs?created=>{week_ago}&per_page=100"
            resp = requests.get(api_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                runs = resp.json().get("workflow_runs", [])
                result["actions_runs_ok"] = sum(1 for r in runs if r.get("conclusion") == "success")
                result["actions_runs_fail"] = sum(1 for r in runs if r.get("conclusion") == "failure")
    except Exception as e:
        log.warning("%s actions error: %s", web["name"], str(e)[:60])

    return result


def main():
    log.info("Generando reporte semanal de webs...")
    results = []

    for web in WEBS:
        log.info("Comprobando %s...", web["name"])
        data = check_web(web)
        results.append(data)
        log.info("  %s: %s, %d artículos", web["name"], "OK" if data["online"] else "DOWN", data["articles_total"])

    # Construir mensaje
    date_str = datetime.utcnow().strftime("%d/%m/%Y")
    lines = [f"🌐 <b>Reporte Webs Semanal</b> — {date_str}\n"]

    total_articles = 0
    total_this_week = 0

    for r in results:
        status = "🟢" if r["online"] else "🔴"
        total_articles += r["articles_total"]
        total_this_week += r["articles_this_week"]

        actions_info = ""
        if r["actions_runs_ok"] or r["actions_runs_fail"]:
            actions_info = f"\n   ⚙️ Actions: {r['actions_runs_ok']} OK, {r['actions_runs_fail']} fail"

        lines.append(
            f"{status} <b>{r['name']}</b> — {r['domain']}\n"
            f"   📝 {r['articles_total']} artículos total | {r['articles_this_week']} esta semana"
            f"{actions_info}"
        )

    lines.append(
        f"\n📈 <b>RESUMEN</b>\n"
        f"   Total artículos: {total_articles}\n"
        f"   Nuevos esta semana: {total_this_week}\n"
        f"   Webs online: {sum(1 for r in results if r['online'])}/{len(results)}"
    )

    # Alertas
    down = [r for r in results if not r["online"]]
    if down:
        lines.append(f"\n⚠️ <b>ALERTA</b>: {', '.join(r['name'] for r in down)} DOWN!")

    no_articles = [r for r in results if r["articles_this_week"] == 0]
    if no_articles:
        lines.append(f"⚠️ Sin artículos esta semana: {', '.join(r['name'] for r in no_articles)}")

    msg = "\n".join(lines)
    notify_telegram(msg)
    log.info("Reporte enviado por Telegram")


if __name__ == "__main__":
    main()
