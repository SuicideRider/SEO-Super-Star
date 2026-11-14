"""Headless CLI runner for GitHub Actions daily scheduled cron jobs (`cli_sync.py`).

Executes automated URL audits, keyword trend checks, and Google Search Console
opportunity pulls, writing results directly to Neon Serverless Postgres (`DATABASE_URL`)
and optionally Google Sheets (`gspread`).
"""

import argparse
import json
import os
from core.crawler_audit import audit_url_comprehensive
from core.geo_aeo_schema import score_geo_aeo_readiness
from core.gsc_tracker import fetch_gsc_api_opportunities
from core.keyword_trends import expand_and_score_keywords
from core.storage import StorageManager


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Super Star — Daily Headless Cron Runner")
    parser.add_argument(
        "--url",
        default=os.environ.get("TARGET_AUDIT_URL", "https://example.com"),
        help="Target URL to audit and store in Neon Postgres / SQLite",
    )
    parser.add_argument(
        "--seed-keyword",
        default=os.environ.get("TARGET_SEED_KEYWORD", "wood pressed cooking oil"),
        help="Seed keyword to expand and score daily",
    )
    parser.add_argument(
        "--gsc-site",
        default=os.environ.get("GSC_SITE_URL", ""),
        help="Optional Google Search Console property URL",
    )
    args = parser.parse_args()

    storage = StorageManager()

    print(f"[1/3] Auditing target URL: {args.url}")
    audit_res = audit_url_comprehensive(args.url, run_pagespeed=True)
    geo_res = score_geo_aeo_readiness(audit_res, target_keyword=args.seed_keyword)
    audit_id = storage.save_audit(
        audit_res,
        geo_score=geo_res["total_geo_score"],
        generated_jsonld=geo_res["generated_jsonld"],
    )
    print(f"  -> Saved URL Audit ID #{audit_id} (GEO Score: {geo_res['total_geo_score']}/100)")

    print(f"[2/3] Expanding seed keyword: '{args.seed_keyword}'")
    kw_bundle = expand_and_score_keywords(args.seed_keyword, gl="in", include_questions=True)
    saved_kws = storage.save_keywords(args.seed_keyword, kw_bundle.get("keywords", []))
    print(f"  -> Saved {saved_kws} keyword opportunity rows")

    if args.gsc_site:
        print(f"[3/3] Fetching Google Search Console opportunities for {args.gsc_site}")
        gsc_res = fetch_gsc_api_opportunities(args.gsc_site, days=30)
        print(f"  -> GSC Status: {gsc_res.get('status')} | Summary: {json.dumps(gsc_res.get('summary', {}))}")
    else:
        print("[3/3] Skipping GSC API pull (no GSC_SITE_URL set).")


if __name__ == "__main__":
    main()
