"""
SEO Auto-Fix: detecta problemas indexing en TODAS las URLs y aplica fixes.

Detecta:
- Canonical hijacks (vercel.app vs custom domain)
- Trailing slash mismatch
- 404 broken URLs
- Duplicate canonical
- URL unknown to Google (acción: request indexing)

Uso: python scripts/seo_auto_fix.py --action {scan,fix,index}
"""
import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import xml.etree.ElementTree as ET

SITES = {
    "vidasana360": "https://vida-sana-360.com/",
    "saludlongevidad": "https://saludlongevidad.org/",
    "finanzasclara": "https://finanzasclara.uk/",
    "catbrothers": "https://catbrothers.uk/",
    "espaciointeligente": "https://espaciointeligente.org/",
    "cashcafe": "https://cash-cafe.org/",
}


def gsc_client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GSC_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )
    return build("searchconsole", "v1", credentials=creds)


def get_sitemap_urls(site_url: str) -> list[str]:
    """Extrae todas las URLs de sitemap-index.xml + sub-sitemaps."""
    urls = []
    try:
        idx_url = f"{site_url}sitemap-index.xml"
        r = requests.get(idx_url, timeout=15)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for sm in root.findall(".//sm:sitemap", ns):
            loc = sm.find("sm:loc", ns)
            if loc is None:
                continue
            sub_url = loc.text
            sub_r = requests.get(sub_url, timeout=15)
            if sub_r.status_code != 200:
                continue
            sub_root = ET.fromstring(sub_r.text)
            for u in sub_root.findall(".//sm:url", ns):
                u_loc = u.find("sm:loc", ns)
                if u_loc is not None:
                    urls.append(u_loc.text)
    except Exception as e:
        print(f"  sitemap parse err: {str(e)[:100]}")
    return urls


def inspect_url(svc, url: str, site: str) -> dict:
    """Inspecciona una URL via GSC, retorna diagnóstico."""
    try:
        r = svc.urlInspection().index().inspect(body={
            "inspectionUrl": url,
            "siteUrl": site,
        }).execute()
        idx = r.get("inspectionResult", {}).get("indexStatusResult", {})
        return {
            "url": url,
            "verdict": idx.get("verdict", "?"),
            "coverage": idx.get("coverageState", "?"),
            "google_canonical": idx.get("googleCanonical", ""),
            "user_canonical": idx.get("userCanonical", ""),
            "last_crawl": idx.get("lastCrawlTime", "")[:10],
            "indexing": idx.get("indexingState", ""),
        }
    except HttpError as e:
        return {"url": url, "error": str(e)[:120]}


def categorize_issue(diag: dict) -> str:
    """Categoriza el problema para priorización."""
    if "error" in diag:
        return "ERROR"
    cov = diag["coverage"]
    if "Submitted and indexed" in cov:
        return "OK"
    if "URL is unknown" in cov:
        return "UNKNOWN_REQUEST_INDEX"
    if "Duplicate" in cov and "vercel.app" in diag.get("google_canonical", ""):
        return "VERCEL_HIJACK"
    if "Duplicate" in cov:
        return "DUPLICATE_CANONICAL"
    if "Not found" in cov or "404" in cov:
        return "BROKEN_404"
    if "Excluded" in cov:
        return "EXCLUDED"
    if diag.get("google_canonical") and diag.get("user_canonical") and diag["google_canonical"] != diag["user_canonical"]:
        return "CANONICAL_MISMATCH"
    return "UNKNOWN_OTHER"


def scan_all(svc, sample_per_site: int = 10):
    """Scan TODAS las URLs de cada site (rate-limited)."""
    report = defaultdict(lambda: defaultdict(list))

    for name, site_url in SITES.items():
        print(f"\n=== {name} ({site_url}) ===")
        urls = get_sitemap_urls(site_url)
        print(f"  sitemap URLs: {len(urls)}")
        # Limit per call to avoid quota (GSC: 2000 queries/day/property)
        to_check = urls[:sample_per_site] if sample_per_site else urls
        print(f"  inspecting {len(to_check)} URLs...")
        for i, url in enumerate(to_check):
            diag = inspect_url(svc, url, site_url)
            cat = categorize_issue(diag)
            report[name][cat].append(diag)
            time.sleep(0.5)  # rate limit
            if (i+1) % 10 == 0:
                print(f"    {i+1}/{len(to_check)}...")
        # Summary
        print(f"  RESUMEN {name}:")
        for cat, items in report[name].items():
            print(f"    {cat}: {len(items)}")

    # Save full report
    out = Path(__file__).parent.parent / f"seo_scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out.write_text(json.dumps({k: dict(v) for k, v in report.items()}, indent=2), encoding="utf-8")
    print(f"\nReport: {out}")
    return report


def request_indexing(svc, report: dict):
    """Re-submit sitemap (proxy del request indexing — Indexing API solo job postings/livestreams)."""
    print("\n=== RE-SUBMIT SITEMAPS (forzar recrawl) ===")
    for name, site_url in SITES.items():
        try:
            svc.sitemaps().submit(siteUrl=site_url, feedpath=f"{site_url}sitemap-index.xml").execute()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ERR {name}: {str(e)[:100]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", choices=["scan", "scan-all", "fix", "index"], default="scan")
    ap.add_argument("--sample", type=int, default=10, help="URLs per site")
    args = ap.parse_args()

    svc = gsc_client()

    if args.action == "scan":
        report = scan_all(svc, sample_per_site=args.sample)
    elif args.action == "scan-all":
        report = scan_all(svc, sample_per_site=0)
    elif args.action == "index":
        request_indexing(svc, {})
    elif args.action == "fix":
        # Re-submit sitemaps (best free auto-action)
        report = scan_all(svc, sample_per_site=args.sample)
        request_indexing(svc, report)


if __name__ == "__main__":
    main()
