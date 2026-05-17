"""
Dashboard semanal — métricas consolidadas de TODO el proyecto.
Genera dashboard.html con gráficos Chart.js.

Secciones:
- YT Canales: subs, views, retention, growth 28d, monetización readiness
- Webs SEO: clicks, impressions, position avg, top queries
- Afiliados: tags aplicados por canal/web
- Acciones esta semana: commits relevantes + changes

Uso: python scripts/dashboard.py [--open]
"""
import os, sys, json, argparse, webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

YT_CHANNELS = {
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

SITES = {
    "vidasana360": "https://vida-sana-360.com/",
    "saludlongevidad": "https://saludlongevidad.org/",
    "finanzasclara": "https://finanzasclara.uk/",
    "catbrothers": "https://catbrothers.uk/",
    "espaciointeligente": "https://espaciointeligente.org/",
    "cashcafe": "https://cash-cafe.org/",
}

# Partner Program thresholds (2026)
YPP_SHORTS = {"subs": 1000, "shorts_views_90d": 10_000_000}  # 10M views shorts
YPP_LF = {"subs": 1000, "watch_hours": 4000}  # 4000h watch time


def yt_creds(env_name):
    token = os.getenv(f"YT_TOKEN_{env_name}")
    if not token: return None
    return Credentials(
        token=None, refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube","https://www.googleapis.com/auth/yt-analytics.readonly"],
    )


def pull_yt(env_name, ch_name):
    creds = yt_creds(env_name)
    if not creds: return None
    try:
        yt = build("youtube","v3", credentials=creds)
        yta = build("youtubeAnalytics","v2", credentials=creds)
        info = yt.channels().list(part="id,statistics,snippet", mine=True).execute()["items"][0]
        ch_id = info["id"]
        stats = info["statistics"]
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=28)
        m = yta.reports().query(
            ids=f"channel=={ch_id}",
            startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,averageViewPercentage",
            dimensions="day",
        ).execute().get("rows", [])
        if not m: return {"name": ch_name, "subs": int(stats.get("subscriberCount",0)), "views_total": int(stats.get("viewCount",0)), "subs_28d": 0, "views_28d": 0, "watch_min_28d": 0, "ret": 0}
        return {
            "name": ch_name,
            "subs": int(stats.get("subscriberCount",0)),
            "views_total": int(stats.get("viewCount",0)),
            "subs_28d": sum(r[3] for r in m) - sum(r[4] for r in m),
            "views_28d": sum(r[1] for r in m),
            "watch_min_28d": sum(r[2] for r in m),
            "ret": sum(r[5] for r in m) / len(m),
            "days": [r[0] for r in m],
            "views_daily": [r[1] for r in m],
            "subs_daily": [r[3]-r[4] for r in m],
        }
    except Exception as e:
        return {"name": ch_name, "error": str(e)[:120]}


def gsc_creds():
    return Credentials(
        token=None, refresh_token=os.environ["GSC_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )


def pull_gsc(site):
    svc = build("searchconsole","v1", credentials=gsc_creds())
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=28)
    try:
        r = svc.searchanalytics().query(siteUrl=site, body={
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["query"], "rowLimit": 20,
        }).execute()
        rows = r.get("rows", [])
        total_c = sum(row["clicks"] for row in rows)
        total_i = sum(row["impressions"] for row in rows)
        # Pages
        rp = svc.searchanalytics().query(siteUrl=site, body={
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["page"], "rowLimit": 5,
        }).execute()
        return {
            "clicks": total_c, "impressions": total_i,
            "ctr": total_c/total_i*100 if total_i else 0,
            "top_queries": [{"q": r["keys"][0][:40], "c": r["clicks"], "i": r["impressions"], "pos": r.get("position",0)} for r in rows[:5]],
            "top_pages": [{"p": r["keys"][0].replace(site,"/")[:60], "c": r["clicks"], "i": r["impressions"]} for r in rp.get("rows",[])[:5]],
        }
    except Exception as e:
        return {"error": str(e)[:120]}


def yp_status(d):
    """Estado Partner Program."""
    if "error" in d: return "—"
    subs = d.get("subs", 0)
    if subs < 500: return "🔴 lejos"
    if subs < 1000: return f"🟡 {1000-subs} subs faltan"
    return f"🟢 ELEGIBLE ({subs} subs)"


def adsense_status(c):
    if "error" in c: return "—"
    clicks = c.get("clicks", 0)
    if clicks == 0: return "🔴 no apto"
    if clicks < 50: return f"🟡 tráfico bajo ({clicks}c)"
    return f"🟢 listo solicitar"


def render_html(yt_data, gsc_data, generated_at):
    yt_rows = ""
    for d in yt_data:
        if "error" in d:
            yt_rows += f'<tr><td>{d["name"]}</td><td colspan="7" class="err">ERR: {d["error"][:60]}</td></tr>'
            continue
        delta_color = "good" if d["subs_28d"] > 0 else "bad"
        yt_rows += f'''<tr>
            <td><b>{d["name"]}</b></td>
            <td>{d["subs"]:,}</td>
            <td class="{delta_color}">{d["subs_28d"]:+,}</td>
            <td>{d["views_28d"]:,}</td>
            <td>{d["watch_min_28d"]:,}</td>
            <td>{d["ret"]:.1f}%</td>
            <td>{yp_status(d)}</td>
        </tr>'''

    gsc_rows = ""
    for site, gd in gsc_data.items():
        if "error" in gd:
            gsc_rows += f'<tr><td>{site}</td><td colspan="4" class="err">{gd["error"][:60]}</td></tr>'
            continue
        gsc_rows += f'''<tr>
            <td><b>{site}</b></td>
            <td>{gd["clicks"]}</td>
            <td>{gd["impressions"]}</td>
            <td>{gd["ctr"]:.2f}%</td>
            <td>{adsense_status(gd)}</td>
        </tr>'''

    # Chart data
    chart_subs = json.dumps([{"label": d["name"], "value": d.get("subs", 0)} for d in yt_data if "error" not in d])
    chart_growth = json.dumps([{"label": d["name"], "value": d.get("subs_28d", 0)} for d in yt_data if "error" not in d])
    chart_views_web = json.dumps([{"label": site, "clicks": gd.get("clicks",0), "imp": gd.get("impressions",0)} for site, gd in gsc_data.items() if "error" not in gd])

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Dashboard — Imperio Digital</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, system-ui, sans-serif; }}
body {{ background: #0a0e1a; color: #e4e8f0; padding: 24px; }}
h1 {{ color: #4ade80; margin-bottom: 8px; }}
h2 {{ color: #60a5fa; margin: 32px 0 12px; }}
.meta {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
.card {{ background: #131826; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #1e293b; }}
th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
.good {{ color: #4ade80; }}
.bad {{ color: #f87171; }}
.err {{ color: #fb923c; font-style: italic; }}
canvas {{ max-height: 280px; }}
.summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 16px 0; }}
.stat {{ background: #131826; border: 1px solid #1e293b; padding: 16px; border-radius: 8px; }}
.stat b {{ display: block; font-size: 24px; color: #4ade80; }}
.stat span {{ color: #94a3b8; font-size: 12px; }}
</style>
</head>
<body>
<h1>📊 Dashboard Imperio Digital</h1>
<p class="meta">Generado: {generated_at} | Próxima actualización: weekly cron</p>

<div class="summary">
<div class="stat"><b>{sum(d.get("subs",0) for d in yt_data if "error" not in d):,}</b><span>Subs totales YT</span></div>
<div class="stat"><b>{sum(d.get("subs_28d",0) for d in yt_data if "error" not in d):+,}</b><span>Δ Subs 28d</span></div>
<div class="stat"><b>{sum(gd.get("clicks",0) for gd in gsc_data.values() if "error" not in gd)}</b><span>Clicks web 28d</span></div>
<div class="stat"><b>{sum(gd.get("impressions",0) for gd in gsc_data.values() if "error" not in gd):,}</b><span>Impressions web 28d</span></div>
</div>

<h2>📺 YouTube — Canales</h2>
<div class="card">
<table>
<thead><tr><th>Canal</th><th>Subs</th><th>Δ 28d</th><th>Views 28d</th><th>Watch min</th><th>Retención</th><th>Partner Prog</th></tr></thead>
<tbody>{yt_rows}</tbody>
</table>
</div>

<div class="grid">
<div class="card"><h3 style="color:#60a5fa;margin-bottom:12px;font-size:14px;">Subs Totales</h3><canvas id="cSubs"></canvas></div>
<div class="card"><h3 style="color:#60a5fa;margin-bottom:12px;font-size:14px;">Crecimiento 28d</h3><canvas id="cGrowth"></canvas></div>
</div>

<h2>🌐 Webs — Search Console</h2>
<div class="card">
<table>
<thead><tr><th>Web</th><th>Clicks 28d</th><th>Impressions</th><th>CTR</th><th>AdSense</th></tr></thead>
<tbody>{gsc_rows}</tbody>
</table>
</div>

<div class="grid">
<div class="card"><h3 style="color:#60a5fa;margin-bottom:12px;font-size:14px;">Tráfico Web 28d</h3><canvas id="cWebs"></canvas></div>
<div class="card">
<h3 style="color:#60a5fa;margin-bottom:12px;font-size:14px;">💰 Monetización Status</h3>
<table style="font-size:12px">
<tr><th>Programa</th><th>Requisito</th><th>Status</th></tr>
<tr><td>YT Partner LF</td><td>1k subs + 4000h watch/12m</td><td>VidaSana cerca (188 subs)</td></tr>
<tr><td>YT Partner Shorts</td><td>1k subs + 10M views/90d</td><td>Lejos</td></tr>
<tr><td>Amazon ES</td><td>3 ventas/180d</td><td>vladys-21 activo en 2 webs ES</td></tr>
<tr><td>Amazon US</td><td>3 ventas/180d</td><td>vds96-20 activo en 3 webs EN</td></tr>
<tr><td>AdSense</td><td>~20 art + tráfico orgánico</td><td>Esperar 1-3 meses crawl</td></tr>
</table>
</div>
</div>

<h2>🔗 Afiliados Amazon — Mapeo</h2>
<div class="card">
<table>
<thead><tr><th>Sitio/Canal</th><th>Idioma</th><th>Tag</th><th>Marketplace</th></tr></thead>
<tbody>
<tr><td>VidaSana360 (web+YT)</td><td>ES</td><td>vladys-21</td><td>amazon.es</td></tr>
<tr><td>SaludLongevidad (web+YT)</td><td>ES</td><td>vladys-21</td><td>amazon.es</td></tr>
<tr><td>FinanzasClara (web+YT)</td><td>EN</td><td>vds96-20</td><td>amazon.com</td></tr>
<tr><td>CatBrothers (web+YT)</td><td>EN</td><td>vds96-20</td><td>amazon.com</td></tr>
<tr><td>EspacioInteligente (web+YT)</td><td>EN</td><td>vds96-20</td><td>amazon.com</td></tr>
<tr><td>CashCafe, DarkFiles, MindWired, DisasterDecode</td><td>EN</td><td>vds96-20</td><td>amazon.com</td></tr>
<tr><td>DonVladys</td><td>ES</td><td>vladys-21</td><td>amazon.es</td></tr>
</tbody>
</table>
</div>

<script>
const subs = {chart_subs};
const growth = {chart_growth};
const webs = {chart_views_web};
const cfg = {{ plugins: {{ legend: {{ display: false }} }} }};
new Chart(document.getElementById('cSubs'), {{
  type: 'bar',
  data: {{ labels: subs.map(d=>d.label), datasets: [{{ data: subs.map(d=>d.value), backgroundColor: '#4ade80' }}] }},
  options: cfg,
}});
new Chart(document.getElementById('cGrowth'), {{
  type: 'bar',
  data: {{ labels: growth.map(d=>d.label), datasets: [{{ data: growth.map(d=>d.value), backgroundColor: growth.map(d=>d.value>=0?'#4ade80':'#f87171') }}] }},
  options: cfg,
}});
new Chart(document.getElementById('cWebs'), {{
  type: 'bar',
  data: {{ labels: webs.map(d=>d.label), datasets: [
    {{ label: 'Clicks', data: webs.map(d=>d.clicks), backgroundColor: '#4ade80' }},
    {{ label: 'Impressions/100', data: webs.map(d=>d.imp/100), backgroundColor: '#60a5fa' }},
  ] }},
  options: {{ plugins: {{ legend: {{ display: true }} }} }},
}});
</script>
</body>
</html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    print("Pulling YT Analytics...")
    yt_data = []
    for env, name in YT_CHANNELS.items():
        d = pull_yt(env, name)
        if d: yt_data.append(d)
        print(f"  {name}: {'OK' if d and 'error' not in d else 'ERR'}")

    print("Pulling GSC...")
    gsc_data = {}
    for site_key, site_url in SITES.items():
        gsc_data[site_key] = pull_gsc(site_url)
        print(f"  {site_key}: {'OK' if 'error' not in gsc_data[site_key] else 'ERR'}")

    out = Path(__file__).parent.parent / "dashboard.html"
    html = render_html(yt_data, gsc_data, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    out.write_text(html, encoding="utf-8")
    # Archivo timestamped histórico
    history = Path(__file__).parent.parent / "dashboard_history"
    history.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (history / f"dashboard_{stamp}.html").write_text(html, encoding="utf-8")
    print(f"\nDashboard: {out}")
    print(f"Histórico: {history / f'dashboard_{stamp}.html'}")
    if args.open:
        webbrowser.open(f"file://{out.absolute()}")
    # macOS notification
    import subprocess
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "Dashboard generado. Abrir en {out}" with title "📊 Dashboard Semanal"'
        ], check=False, timeout=5)
    except Exception:
        pass


if __name__ == "__main__":
    main()
