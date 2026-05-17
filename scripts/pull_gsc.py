"""
Google Search Console — pull indexing + performance + index URLs.
Uso:
  python scripts/pull_gsc.py --action audit     # cobertura indexing all sites
  python scripts/pull_gsc.py --action perf      # performance reports (clicks, impressions, CTR)
  python scripts/pull_gsc.py --action submit    # request indexing top URLs
  python scripts/pull_gsc.py --action sitemap   # submit sitemap each site
"""
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/webmasters"]

SITES = {
    "vidasana360": "https://vida-sana-360.com/",
    "saludlongevidad": "https://saludlongevidad.org/",
    "finanzasclara": "https://finanzasclara.uk/",
    "catbrothers": "https://catbrothers.uk/",
    "espaciointeligente": "https://espaciointeligente.org/",
    "cashcafe": "https://cash-cafe.org/",
}


def client():
    # Prefer OAuth (user) over service account (Search Console UI no acepta SA)
    refresh = os.getenv("GSC_REFRESH_TOKEN")
    if refresh:
        creds = Credentials(
            token=None,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["YOUTUBE_CLIENT_ID"],
            client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
            scopes=SCOPES,
        )
    else:
        sa_path = os.environ["GSC_SERVICE_ACCOUNT_JSON"]
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds)


def list_sites(svc):
    r = svc.sites().list().execute()
    return [s["siteUrl"] for s in r.get("siteEntry", [])]


def audit_indexing(svc):
    """Inspeccionar URLs muestra de cada site para coverage."""
    print("\n=== AUDIT INDEXING ===")
    for name, url in SITES.items():
        print(f"\n--- {name} ({url}) ---")
        try:
            # Sample top URLs from sitemap (just root + blog for sample)
            for sample_path in ["", "blog/"]:
                target = f"{url}{sample_path}".rstrip("/")
                try:
                    r = svc.urlInspection().index().inspect(body={
                        "inspectionUrl": target if not sample_path else f"{url}{sample_path}",
                        "siteUrl": url,
                    }).execute()
                    res = r.get("inspectionResult", {})
                    idx = res.get("indexStatusResult", {})
                    status = idx.get("verdict", "?")
                    cov = idx.get("coverageState", "?")
                    print(f"  [{target}] verdict={status} | coverage={cov}")
                except HttpError as e:
                    print(f"  [{target}] ERR: {str(e)[:120]}")
        except Exception as e:
            print(f"  ERR {name}: {str(e)[:120]}")


def perf(svc, days=28):
    """Performance report: queries, clicks, impressions, CTR, position."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    print(f"\n=== PERFORMANCE {days}d ({start} → {end}) ===")
    for name, url in SITES.items():
        try:
            r = svc.searchanalytics().query(siteUrl=url, body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 10,
            }).execute()
            rows = r.get("rows", [])
            print(f"\n--- {name} ---")
            if not rows:
                print("  NO DATA")
                continue
            # Aggregate totals
            total_clicks = sum(r["clicks"] for r in rows)
            total_imp = sum(r["impressions"] for r in rows)
            avg_ctr = total_clicks / total_imp * 100 if total_imp else 0
            print(f"  Total: {total_clicks} clicks, {total_imp} imp, CTR {avg_ctr:.2f}%")
            print(f"  TOP 5 queries:")
            for row in rows[:5]:
                q = row["keys"][0][:50]
                c = row["clicks"]
                i = row["impressions"]
                ctr = c / i * 100 if i else 0
                pos = row.get("position", 0)
                print(f"    '{q}' — {c}c {i}imp CTR {ctr:.1f}% pos {pos:.1f}")
        except HttpError as e:
            print(f"  ERR {name}: {str(e)[:120]}")


def perf_pages(svc, days=28):
    """Performance by page."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    print(f"\n=== TOP PAGES {days}d ===")
    for name, url in SITES.items():
        try:
            r = svc.searchanalytics().query(siteUrl=url, body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["page"],
                "rowLimit": 10,
            }).execute()
            rows = r.get("rows", [])
            print(f"\n--- {name} ---")
            if not rows:
                print("  NO DATA INDEXED")
                continue
            for row in rows[:10]:
                page = row["keys"][0].replace(url, "/")
                c = row["clicks"]
                i = row["impressions"]
                pos = row.get("position", 0)
                print(f"    {page[:60]} — {c}c {i}imp pos {pos:.1f}")
        except HttpError as e:
            print(f"  ERR {name}: {str(e)[:120]}")


def list_sitemaps(svc):
    """List sitemaps + indexing status."""
    print("\n=== SITEMAPS ===")
    for name, url in SITES.items():
        try:
            r = svc.sitemaps().list(siteUrl=url).execute()
            print(f"\n--- {name} ---")
            for sm in r.get("sitemap", []):
                path = sm.get("path", "?")
                submitted = sm.get("lastSubmitted", "?")
                last_dl = sm.get("lastDownloaded", "?")
                indexed = sm.get("contents", [{}])[0].get("submitted", "?")
                warnings = sm.get("warnings", 0)
                errors = sm.get("errors", 0)
                print(f"  {path} | submitted {submitted[:10]} | downloaded {last_dl[:10]} | warn {warnings} err {errors}")
        except HttpError as e:
            print(f"  ERR {name}: {str(e)[:120]}")


def submit_sitemap(svc):
    """(Re-)submit sitemap to each site."""
    print("\n=== SUBMIT SITEMAPS ===")
    for name, url in SITES.items():
        sm = f"{url}sitemap-index.xml"
        try:
            svc.sitemaps().submit(siteUrl=url, feedpath=sm).execute()
            print(f"  ✓ {name}: {sm}")
        except HttpError as e:
            print(f"  ERR {name}: {str(e)[:120]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", default="all", choices=["audit", "perf", "pages", "sitemap", "submit", "list", "all"])
    ap.add_argument("--days", type=int, default=28)
    args = ap.parse_args()

    svc = client()

    if args.action in ("list", "all"):
        print("=== SITES VERIFIED ===")
        for s in list_sites(svc):
            print(f"  {s}")

    if args.action in ("sitemap", "all"):
        list_sitemaps(svc)
    if args.action in ("audit", "all"):
        audit_indexing(svc)
    if args.action in ("perf", "all"):
        perf(svc, args.days)
        perf_pages(svc, args.days)
    if args.action == "submit":
        submit_sitemap(svc)


if __name__ == "__main__":
    main()
