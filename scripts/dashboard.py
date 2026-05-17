"""
Dashboard semanal — métricas consolidadas del Imperio Digital.
Genera dashboard.html con gráficos, filtros temporales, hitos, métricas divertidas.

Uso: python scripts/dashboard.py [--open] [--days 28]
"""
import os, sys, json, argparse, webbrowser, subprocess
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

PROJECT_START = datetime(2026, 4, 28, tzinfo=timezone.utc)  # arranque empire


def yt_creds(env_name):
    token = os.getenv(f"YT_TOKEN_{env_name}")
    if not token: return None
    return Credentials(
        token=None, refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube","https://www.googleapis.com/auth/yt-analytics.readonly"],
    )


def pull_yt(env_name, ch_name, days=28):
    creds = yt_creds(env_name)
    if not creds: return None
    try:
        yt = build("youtube","v3", credentials=creds)
        yta = build("youtubeAnalytics","v2", credentials=creds)
        info = yt.channels().list(part="id,statistics,snippet", mine=True).execute()["items"][0]
        ch_id = info["id"]
        stats = info["statistics"]
        snippet = info["snippet"]
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)
        m = yta.reports().query(
            ids=f"channel=={ch_id}",
            startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,averageViewPercentage",
            dimensions="day",
        ).execute().get("rows", [])
        top = yta.reports().query(
            ids=f"channel=={ch_id}",
            startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,averageViewPercentage,averageViewDuration",
            dimensions="video", sort="-views", maxResults=3,
        ).execute().get("rows", [])
        worst = []  # API no permite sort ascending sin filters extra
        return {
            "name": ch_name,
            "env": env_name,
            "subs": int(stats.get("subscriberCount",0)),
            "views_total": int(stats.get("viewCount",0)),
            "videos_total": int(stats.get("videoCount",0)),
            "published_at": snippet.get("publishedAt","")[:10],
            "subs_28d": sum(r[3] for r in m) - sum(r[4] for r in m),
            "subs_gained_28d": sum(r[3] for r in m),
            "views_28d": sum(r[1] for r in m),
            "watch_min_28d": sum(r[2] for r in m),
            "ret": sum(r[5] for r in m) / len(m) if m else 0,
            "days": [r[0] for r in m],
            "views_daily": [r[1] for r in m],
            "subs_daily": [r[3]-r[4] for r in m],
            "top_videos": [{"id": r[0], "views": r[1], "wm": r[2], "ret": r[3], "dur": r[4]} for r in top],
            "worst_video": {"id": worst[0][0], "views": worst[0][1], "ret": worst[0][2]} if worst else None,
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


def pull_gsc(site, days=28):
    svc = build("searchconsole","v1", credentials=gsc_creds())
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    try:
        r = svc.searchanalytics().query(siteUrl=site, body={
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["query"], "rowLimit": 20,
        }).execute()
        rows = r.get("rows", [])
        total_c = sum(row["clicks"] for row in rows)
        total_i = sum(row["impressions"] for row in rows)
        rp = svc.searchanalytics().query(siteUrl=site, body={
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": ["page"], "rowLimit": 5,
        }).execute()
        return {
            "clicks": total_c, "impressions": total_i,
            "ctr": total_c/total_i*100 if total_i else 0,
            "avg_pos": sum(r.get("position",0)*r["impressions"] for r in rows)/total_i if total_i else 0,
            "top_queries": [{"q": r["keys"][0][:40], "c": r["clicks"], "i": r["impressions"], "pos": r.get("position",0)} for r in rows[:5]],
            "top_pages": [{"p": r["keys"][0].replace(site,"/")[:50], "c": r["clicks"], "i": r["impressions"]} for r in rp.get("rows",[])[:5]],
        }
    except Exception as e:
        return {"error": str(e)[:120]}


def count_articles():
    """Cuenta artículos publicados por web."""
    counts = {}
    for site_key in SITES.keys():
        repo_map = {"vidasana360": "vidasana360-web", "saludlongevidad": "saludlongevidad-web",
                    "finanzasclara": "finanzasclara-web", "catbrothers": "catbrothers-web",
                    "espaciointeligente": "hogarinteligente-web", "cashcafe": "cashcafe-web"}
        repo = repo_map.get(site_key)
        if not repo: continue
        path = Path(f"/Users/vladys/Proyectos/{repo}/src/content/blog")
        if path.exists():
            counts[site_key] = len(list(path.glob("*.md")))
    return counts


def get_recent_commits(repo_path: str, days: int = 7) -> int:
    """Cuenta commits en repo últimos N días."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        r = subprocess.run(["git", "-C", repo_path, "log", f"--since={since}", "--oneline"],
                          capture_output=True, text=True, timeout=10)
        return len([l for l in r.stdout.split("\n") if l.strip()])
    except Exception:
        return 0


def goal_pct(current, target):
    return min(100, current / target * 100) if target else 0


def project_revenue(yt_data, gsc_data):
    """Estimación revenue mensual proyectado."""
    # YT: $1.5/1000 views cuando monetizado (~$0.5-2.5 ronda)
    yt_views_monthly = sum(d.get("views_28d", 0) for d in yt_data if "error" not in d)
    # Solo cuenta canales con 1k+ subs (eligibles)
    monetizable_views = sum(d.get("views_28d", 0) for d in yt_data if "error" not in d and d.get("subs", 0) >= 1000)
    yt_revenue = monetizable_views * 1.5 / 1000
    # Web AdSense: ~$10 RPM tráfico orgánico
    web_clicks_monthly = sum(gd.get("clicks", 0) for gd in gsc_data.values() if "error" not in gd)
    web_revenue = web_clicks_monthly * 0.5  # $0.5 / click ad (conservative)
    # Amazon: 4-8% commission, suponer 1% CTR + $30 avg order + 5% comm
    web_imp = sum(gd.get("impressions", 0) for gd in gsc_data.values() if "error" not in gd)
    amazon_revenue = web_imp * 0.01 * 30 * 0.05
    return {
        "yt_now": yt_revenue,
        "web_ads": web_revenue,
        "amazon": amazon_revenue,
        "total_now": yt_revenue + web_revenue + amazon_revenue,
    }


def render_html(yt_data, gsc_data, articles, weekly_commits, generated_at, days=28):
    # Stats globales
    total_subs = sum(d.get("subs",0) for d in yt_data if "error" not in d)
    total_subs_28d = sum(d.get("subs_28d",0) for d in yt_data if "error" not in d)
    total_views_28d = sum(d.get("views_28d",0) for d in yt_data if "error" not in d)
    total_views_lifetime = sum(d.get("views_total",0) for d in yt_data if "error" not in d)
    total_videos = sum(d.get("videos_total",0) for d in yt_data if "error" not in d)
    total_articles = sum(articles.values())
    total_clicks = sum(gd.get("clicks",0) for gd in gsc_data.values() if "error" not in gd)
    total_imp = sum(gd.get("impressions",0) for gd in gsc_data.values() if "error" not in gd)
    days_running = (datetime.now(timezone.utc) - PROJECT_START).days
    revenue = project_revenue(yt_data, gsc_data)

    # Best/worst — divertido
    valid_yt = [d for d in yt_data if "error" not in d and d.get("top_videos")]
    best_channel = max(valid_yt, key=lambda d: d.get("views_28d",0)) if valid_yt else None
    most_grown = max(valid_yt, key=lambda d: d.get("subs_28d",0)) if valid_yt else None
    biggest_l = min([d for d in valid_yt if d.get("worst_video")], key=lambda d: d["worst_video"]["views"]) if any(d.get("worst_video") for d in valid_yt) else None

    # Goal: 1k subs (YPP)
    yt_rows = ""
    for d in sorted(yt_data, key=lambda x: x.get("subs",0), reverse=True):
        if "error" in d:
            yt_rows += f'<tr><td>{d["name"]}</td><td colspan="7" class="err">ERR</td></tr>'
            continue
        pct = goal_pct(d["subs"], 1000)
        delta_class = "good" if d["subs_28d"] > 0 else "bad" if d["subs_28d"] < 0 else "neutral"
        yt_rows += f'''<tr>
            <td><b>{d["name"]}</b><br><span class="sub">{d["published_at"]}</span></td>
            <td>{d["subs"]:,}</td>
            <td class="{delta_class}">{d["subs_28d"]:+,}</td>
            <td>{d["views_28d"]:,}</td>
            <td>{d["watch_min_28d"]:,}</td>
            <td>{d["ret"]:.0f}%</td>
            <td>{d["videos_total"]}</td>
            <td><div class="progress"><div class="bar" style="width:{pct}%"></div></div><span class="sub">{int(pct)}% YPP</span></td>
        </tr>'''

    gsc_rows = ""
    for site, gd in sorted(gsc_data.items(), key=lambda x: x[1].get("clicks",0) if "error" not in x[1] else 0, reverse=True):
        if "error" in gd:
            gsc_rows += f'<tr><td>{site}</td><td colspan="5" class="err">ERR</td></tr>'
            continue
        arts = articles.get(site, 0)
        gsc_rows += f'''<tr>
            <td><b>{site}</b></td>
            <td>{arts}</td>
            <td>{gd["clicks"]}</td>
            <td>{gd["impressions"]:,}</td>
            <td>{gd["ctr"]:.2f}%</td>
            <td>{gd["avg_pos"]:.1f}</td>
        </tr>'''

    # Top queries todas las webs
    top_queries_global = []
    for site, gd in gsc_data.items():
        if "error" in gd: continue
        for q in gd.get("top_queries", [])[:3]:
            top_queries_global.append({"site": site, **q})
    top_queries_global.sort(key=lambda x: x["i"], reverse=True)

    queries_html = "".join(f'<tr><td>{q["site"][:15]}</td><td>{q["q"]}</td><td>{q["c"]}</td><td>{q["i"]}</td><td>{q["pos"]:.1f}</td></tr>' for q in top_queries_global[:10])

    # Chart data
    chart_subs = json.dumps([{"label": d["name"], "value": d.get("subs", 0)} for d in yt_data if "error" not in d])
    chart_growth = json.dumps([{"label": d["name"], "value": d.get("subs_28d", 0)} for d in yt_data if "error" not in d])
    chart_views = json.dumps([{"label": d["name"], "value": d.get("views_28d", 0)} for d in yt_data if "error" not in d])
    chart_webs = json.dumps([{"label": site, "clicks": gd.get("clicks",0), "imp": gd.get("impressions",0)} for site, gd in gsc_data.items() if "error" not in gd])

    # Fun stats
    biggest_l_html = ""
    if biggest_l and biggest_l.get("worst_video"):
        wv = biggest_l["worst_video"]
        biggest_l_html = f'<tr><td>💔 Peor video</td><td>{biggest_l["name"]}</td><td>{wv["views"]} views, {wv["ret"]:.1f}% ret</td></tr>'

    best_yt_html = ""
    if best_channel:
        best_yt_html = f'<tr><td>🔥 Canal top views {days}d</td><td>{best_channel["name"]}</td><td>{best_channel["views_28d"]:,} views</td></tr>'
    if most_grown:
        best_yt_html += f'<tr><td>🚀 Más nuevos subs {days}d</td><td>{most_grown["name"]}</td><td>+{most_grown["subs_28d"]} subs</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard — Imperio Digital</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,system-ui,sans-serif}}
body{{background:#0a0e1a;color:#e4e8f0;padding:24px;max-width:1400px;margin:0 auto}}
h1{{color:#4ade80;margin-bottom:4px;font-size:28px}}
h2{{color:#60a5fa;margin:32px 0 12px;font-size:18px}}
h3{{color:#a78bfa;font-size:14px;margin-bottom:12px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
.card{{background:#131826;border:1px solid #1e293b;border-radius:12px;padding:18px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid #1e293b}}
th{{color:#94a3b8;font-weight:600;text-transform:uppercase;font-size:10px}}
.good{{color:#4ade80}}.bad{{color:#f87171}}.neutral{{color:#94a3b8}}.err{{color:#fb923c;font-style:italic}}
.sub{{color:#64748b;font-size:11px}}
canvas{{max-height:240px}}
.summary{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0}}
.stat{{background:#131826;border:1px solid #1e293b;padding:14px;border-radius:8px}}
.stat b{{display:block;font-size:22px;color:#4ade80}}
.stat span{{color:#94a3b8;font-size:11px}}
.stat .delta{{font-size:11px;margin-top:4px}}
.progress{{background:#1e293b;height:6px;border-radius:3px;overflow:hidden;margin-bottom:2px}}
.bar{{background:linear-gradient(90deg,#4ade80,#60a5fa);height:100%;transition:width 0.5s}}
.tabs{{display:flex;gap:8px;margin-bottom:12px}}
.tab{{padding:6px 14px;background:#131826;border:1px solid #1e293b;border-radius:6px;cursor:pointer;font-size:12px;color:#94a3b8}}
.tab.active{{background:#1e3a8a;color:#fff;border-color:#3b82f6}}
.revenue-card{{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);border:1px solid #4ade80}}
.revenue-card .num{{color:#4ade80;font-size:32px;font-weight:bold}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}}
.b-good{{background:#065f46;color:#a7f3d0}}
.b-warn{{background:#78350f;color:#fde68a}}
.b-bad{{background:#7f1d1d;color:#fecaca}}
</style>
</head>
<body>
<h1>📊 Imperio Digital — Dashboard</h1>
<p class="meta">Generado: {generated_at} • Día {days_running} desde lanzamiento ({PROJECT_START.strftime('%Y-%m-%d')}) • Período: últimos {days}d</p>

<div class="summary">
<div class="stat"><b>{total_subs:,}</b><span>Subs YT totales</span><div class="delta {'good' if total_subs_28d > 0 else 'bad'}">{total_subs_28d:+,} ({days}d)</div></div>
<div class="stat"><b>{total_views_28d:,}</b><span>Views YT {days}d</span><div class="delta sub">Total: {total_views_lifetime:,}</div></div>
<div class="stat"><b>{total_videos}</b><span>Videos subidos</span><div class="delta sub">~{total_videos/max(1,days_running):.1f}/día</div></div>
<div class="stat"><b>{total_articles}</b><span>Artículos webs</span><div class="delta sub">{weekly_commits["webs"]} commits esta sem</div></div>
<div class="stat"><b>{total_clicks}</b><span>Clicks SEO {days}d</span><div class="delta sub">{total_imp:,} impressions</div></div>
</div>

<h2>💰 Revenue Proyección (mensual estimado)</h2>
<div class="grid3">
<div class="card revenue-card"><h3>YouTube AdSense (cuando monetice)</h3><div class="num">${revenue["yt_now"]:.0f}</div><span class="sub">Solo canales con 1k+ subs</span></div>
<div class="card revenue-card"><h3>Web AdSense (proyectado)</h3><div class="num">${revenue["web_ads"]:.0f}</div><span class="sub">~$0.5/click orgánico</span></div>
<div class="card revenue-card"><h3>Amazon Afiliados</h3><div class="num">${revenue["amazon"]:.0f}</div><span class="sub">1% CTR × $30 × 5% comm</span></div>
</div>
<div class="card" style="margin-top:12px;text-align:center">
<h3>TOTAL ESTIMADO/MES</h3>
<div style="font-size:48px;color:#4ade80;font-weight:bold">${revenue["total_now"]:.0f}</div>
<span class="sub">Proyección si todo monetizado HOY (la mayoría aún no elegible)</span>
</div>

<h2>📺 YouTube — Canales (ordenados por subs)</h2>
<div class="card">
<table>
<thead><tr><th>Canal</th><th>Subs</th><th>Δ {days}d</th><th>Views {days}d</th><th>Watch min</th><th>Ret</th><th>Videos</th><th>YPP Goal</th></tr></thead>
<tbody>{yt_rows}</tbody>
</table>
</div>

<div class="grid">
<div class="card"><h3>Subs Totales</h3><canvas id="cSubs"></canvas></div>
<div class="card"><h3>Crecimiento {days}d</h3><canvas id="cGrowth"></canvas></div>
</div>

<h2>🌐 Webs — Search Console (ordenadas por clicks)</h2>
<div class="card">
<table>
<thead><tr><th>Web</th><th>Artículos</th><th>Clicks {days}d</th><th>Impressions</th><th>CTR</th><th>Posición avg</th></tr></thead>
<tbody>{gsc_rows}</tbody>
</table>
</div>

<div class="grid">
<div class="card"><h3>Tráfico Web {days}d</h3><canvas id="cWebs"></canvas></div>
<div class="card">
<h3>🔍 Top queries SERP (todas las webs)</h3>
<table style="font-size:11px">
<thead><tr><th>Web</th><th>Query</th><th>C</th><th>Imp</th><th>Pos</th></tr></thead>
<tbody>{queries_html}</tbody>
</table>
</div>
</div>

<h2>🎯 Highlights del Período</h2>
<div class="card">
<table>
<thead><tr><th>Métrica</th><th>Ganador</th><th>Valor</th></tr></thead>
<tbody>
{best_yt_html}
{biggest_l_html}
<tr><td>📚 Más artículos publicados</td><td>{max(articles.items(), key=lambda x: x[1])[0] if articles else '-'}</td><td>{max(articles.values()) if articles else 0} artículos</td></tr>
<tr><td>⚡ Commits totales última semana</td><td>youtube-bot + 5 webs</td><td>{weekly_commits["total"]} commits</td></tr>
</tbody>
</table>
</div>

<h2>💎 Monetización Status</h2>
<div class="card">
<table>
<thead><tr><th>Programa</th><th>Requisito</th><th>Status</th><th>Earnings estimated/mes</th></tr></thead>
<tbody>
<tr><td>YT Partner Program (LF)</td><td>1k subs + 4000h watch/12m</td><td><span class="badge b-warn">VidaSana 188/1000</span></td><td>$0 (locked)</td></tr>
<tr><td>YT Partner Program (Shorts)</td><td>1k subs + 10M views/90d</td><td><span class="badge b-bad">muy lejos</span></td><td>$0 (locked)</td></tr>
<tr><td>Amazon Asociados ES</td><td>3 ventas/180d</td><td><span class="badge b-good">vladys-21 activo</span></td><td>~${revenue["amazon"]/2:.0f}</td></tr>
<tr><td>Amazon Asociados US</td><td>3 ventas/180d</td><td><span class="badge b-good">vds96-20 activo</span></td><td>~${revenue["amazon"]/2:.0f}</td></tr>
<tr><td>Google AdSense (webs)</td><td>~20 art + tráfico orgánico</td><td><span class="badge b-warn">esperar 1-3m crawl</span></td><td>${revenue["web_ads"]:.0f} (cuando apruebe)</td></tr>
</tbody>
</table>
</div>

<script>
const cfgBar = {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ ticks: {{ color: '#94a3b8' }} }}, x: {{ ticks: {{ color: '#94a3b8' }} }} }} }};
const subs = {chart_subs};
new Chart(document.getElementById('cSubs'), {{ type: 'bar', data: {{ labels: subs.map(d=>d.label), datasets: [{{ data: subs.map(d=>d.value), backgroundColor: '#4ade80' }}] }}, options: cfgBar }});
const growth = {chart_growth};
new Chart(document.getElementById('cGrowth'), {{ type: 'bar', data: {{ labels: growth.map(d=>d.label), datasets: [{{ data: growth.map(d=>d.value), backgroundColor: growth.map(d=>d.value>=0?'#4ade80':'#f87171') }}] }}, options: cfgBar }});
const webs = {chart_webs};
new Chart(document.getElementById('cWebs'), {{ type: 'bar', data: {{ labels: webs.map(d=>d.label), datasets: [
  {{ label: 'Clicks', data: webs.map(d=>d.clicks), backgroundColor: '#4ade80' }},
  {{ label: 'Imp/100', data: webs.map(d=>d.imp/100), backgroundColor: '#60a5fa' }},
] }}, options: {{ scales: cfgBar.scales }} }});
</script>
</body>
</html>'''


def render_multi_html(datasets, articles, weekly_commits, generated_at):
    """Render HTML with tab filter para 7d/28d/90d."""
    # Renderiza cada dataset por separado, envuelve en divs con id
    sections = {}
    for days, (yt_data, gsc_data) in datasets.items():
        sections[days] = render_html(yt_data, gsc_data, articles, weekly_commits, generated_at, days)

    # Extraer body de cada uno (entre <body> y </body>)
    panels = {}
    for d, html in sections.items():
        body = html.split("<body>", 1)[1].split("</body>", 1)[0]
        # quitar h1 + meta duplicados
        body_parts = body.split("</p>", 1)
        panels[d] = body_parts[1] if len(body_parts) > 1 else body

    head_template = sections[list(sections.keys())[0]].split("<body>")[0] + "<body>"
    h1_part = sections[list(sections.keys())[0]].split("<body>", 1)[1].split("</p>", 1)[0] + "</p>"

    tabs_html = '''<div class="tabs" style="margin:16px 0;">
<button class="tab active" data-period="7" onclick="switchTab(7)">📅 Última semana (7d)</button>
<button class="tab" data-period="28" onclick="switchTab(28)">📊 Mensual (28d)</button>
<button class="tab" data-period="90" onclick="switchTab(90)">📈 Trimestral (90d)</button>
</div>'''

    import re as _re
    panels_html = ""
    for d, p in panels.items():
        display = "block" if d == 7 else "none"
        # Suffix unique IDs per panel para no colisionar Chart.js
        p_suffixed = _re.sub(r"id=['\"]([a-zA-Z][a-zA-Z0-9]*)['\"]", lambda m: f'id="{m.group(1)}_{d}"', p)
        p_suffixed = _re.sub(r"getElementById\(['\"]([a-zA-Z][a-zA-Z0-9]*)['\"]\)", lambda m: f"getElementById('{m.group(1)}_{d}')", p_suffixed)
        panels_html += f'<div id="panel-{d}" class="panel" style="display:{display}">{p_suffixed}</div>'

    switch_js = '''
<script>
function switchTab(period) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-period="${period}"]`).classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.style.display = 'none');
  document.getElementById(`panel-${period}`).style.display = 'block';
  // Re-init charts inside panel
  setTimeout(() => initChartsInPanel(period), 50);
}
function initChartsInPanel(period) {
  // Trigger window resize so Chart.js re-renders
  window.dispatchEvent(new Event('resize'));
}
</script>'''

    return head_template + h1_part + tabs_html + panels_html + switch_js + "</body></html>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--days", type=int, default=None, help="Single period mode (default: multi 7/28/90)")
    ap.add_argument("--out", default="dashboard.html")
    args = ap.parse_args()

    articles = count_articles()
    print(f"Articles: {articles}")
    bot_commits = get_recent_commits("/Users/vladys/Proyectos/youtube-bot", 7)
    web_commits = sum(get_recent_commits(f"/Users/vladys/Proyectos/{r}", 7) for r in ["vidasana360-web","saludlongevidad-web","finanzasclara-web","catbrothers-web","hogarinteligente-web"])
    weekly_commits = {"bot": bot_commits, "webs": web_commits, "total": bot_commits + web_commits}

    if args.days:
        # Single mode legacy
        periods = [args.days]
    else:
        periods = [7, 28, 90]

    datasets = {}
    for days in periods:
        print(f"\n=== Pulling {days}d ===")
        yt_data = []
        for env, name in YT_CHANNELS.items():
            d = pull_yt(env, name, days)
            if d: yt_data.append(d)
            print(f"  YT {name}: {'OK' if d and 'error' not in d else 'ERR'}")
        gsc_data = {}
        for site_key, site_url in SITES.items():
            gsc_data[site_key] = pull_gsc(site_url, days)
            print(f"  GSC {site_key}: {'OK' if 'error' not in gsc_data[site_key] else 'ERR'}")
        datasets[days] = (yt_data, gsc_data)

    out = Path(__file__).parent.parent / args.out
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    if len(datasets) == 1:
        days = list(datasets.keys())[0]
        yt_data, gsc_data = datasets[days]
        html = render_html(yt_data, gsc_data, articles, weekly_commits, generated_at, days)
    else:
        html = render_multi_html(datasets, articles, weekly_commits, generated_at)
    out.write_text(html, encoding="utf-8")

    history = Path(__file__).parent.parent / "dashboard_history"
    history.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (history / f"dashboard_{stamp}.html").write_text(html, encoding="utf-8")

    print(f"\nDashboard: {out}")
    if args.open:
        webbrowser.open(f"file://{out.absolute()}")
    try:
        subprocess.run(["osascript","-e",f'display notification "Dashboard generado" with title "📊"'], check=False, timeout=5)
    except Exception: pass


if __name__ == "__main__":
    main()
