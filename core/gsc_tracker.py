"""Module 6: Google Search Console Opportunity Miner (Live API + CSV Dropzone).

Connects to the free Google Search Console API (30,000,000 queries/day quota)
or ingests any exported GSC CSV/DataFrame and automatically classifies queries into:
- `Striking Distance (Pos 4–15)`: High-impression queries ready to jump to Top 3
- `CTR Underperformer (Pos 1–5, Low CTR)`: Pages needing title/meta hook & rich schema upgrades
- `Top Winner (Pos 1–3, High CTR)`: Defend & internal-link hubs
- `Cluster Expansion (Pos 16–35)`: Secondary subheadings or new cluster posts
"""

from datetime import date, timedelta
import json
from typing import Any, Dict, Optional
import pandas as pd
from core.config import Settings, get_settings


def classify_gsc_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Normalize and classify a Google Search Console DataFrame into actionable SEO buckets."""
    if df is None or df.empty:
        return {
            "status": "empty",
            "summary": {},
            "dataframe": pd.DataFrame(),
        }

    col_map = {}
    for col in df.columns:
        c_low = str(col).strip().lower()
        if c_low in ("query", "top queries", "queries", "keyword"):
            col_map[col] = "query"
        elif c_low in ("page", "top pages", "pages", "url"):
            col_map[col] = "page"
        elif "click" in c_low:
            col_map[col] = "clicks"
        elif "impression" in c_low:
            col_map[col] = "impressions"
        elif "ctr" in c_low:
            col_map[col] = "ctr"
        elif "position" in c_low:
            col_map[col] = "position"

    work = df.rename(columns=col_map).copy()
    for required_col, default_val in [
        ("query", "(page-level)"),
        ("page", ""),
        ("clicks", 0.0),
        ("impressions", 0.0),
        ("ctr", 0.0),
        ("position", 50.0),
    ]:
        if required_col not in work.columns:
            work[required_col] = default_val

    if work["ctr"].dtype == object:
        work["ctr"] = (
            work["ctr"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .apply(lambda x: float(x) / 100.0 if x.replace(".", "", 1).isdigit() else 0.0)
        )
    for num_col in ["clicks", "impressions", "position"]:
        work[num_col] = (
            work[num_col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .apply(lambda x: float(x) if x.replace(".", "", 1).isdigit() else 0.0)
        )

    impr_floor = min(50.0, float(work["impressions"].quantile(0.25) or 10.0))

    def _bucket_row(row: pd.Series) -> str:
        pos = float(row["position"])
        ctr = float(row["ctr"])
        impr = float(row["impressions"])
        if 4.0 <= pos <= 15.0 and impr >= impr_floor:
            return "Striking Distance (Pos 4–15)"
        if pos <= 5.0 and ctr < 0.035 and impr >= impr_floor:
            return "CTR Underperformer (Pos 1–5)"
        if pos <= 3.5 and ctr >= 0.035:
            return "Top Winner (Pos 1–3)"
        if 15.0 < pos <= 35.0 and impr >= impr_floor:
            return "Cluster Expansion (Pos 16–35)"
        return "Monitor"

    def _recommended_action(bucket: str) -> str:
        if bucket == "Striking Distance (Pos 4–15)":
            return "Add exact query to H2 + 50-word answer block + 3 internal links"
        if bucket == "CTR Underperformer (Pos 1–5)":
            return "Rewrite Title tag hook (<580px) + add FAQPage/Product JSON-LD"
        if bucket == "Cluster Expansion (Pos 16–35)":
            return "Create dedicated section or supporting spoke article"
        if bucket == "Top Winner (Pos 1–3)":
            return "Protect freshness & link out to striking-distance pages"
        return "Track weekly in Neon DB"

    work["opportunity_bucket"] = work.apply(_bucket_row, axis=1)
    work["recommended_action"] = work["opportunity_bucket"].apply(_recommended_action)
    work["ctr_pct"] = (work["ctr"] * 100.0).round(2)
    work["position"] = work["position"].round(1)
    work = work.sort_values(by=["impressions", "clicks"], ascending=[False, False])

    counts = work["opportunity_bucket"].value_counts().to_dict()
    return {
        "status": "ok",
        "summary": {
            "total_rows": len(work),
            "striking_distance_count": int(counts.get("Striking Distance (Pos 4–15)", 0)),
            "ctr_underperformer_count": int(counts.get("CTR Underperformer (Pos 1–5)", 0)),
            "cluster_expansion_count": int(counts.get("Cluster Expansion (Pos 16–35)", 0)),
            "top_winner_count": int(counts.get("Top Winner (Pos 1–3)", 0)),
        },
        "dataframe": work,
    }


def fetch_gsc_api_opportunities(
    site_url: str,
    days: int = 90,
    row_limit: int = 1000,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Pull query+page performance directly from the free Google Search Console API."""
    cfg = settings or get_settings()
    if not cfg.gsc_service_account_json:
        return {
            "status": "no_service_account",
            "message": "No GSC_SERVICE_ACCOUNT_JSON configured. Use the CSV Dropzone or add your free Google Service Account JSON.",
            "summary": {},
            "dataframe": pd.DataFrame(),
        }

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_info = json.loads(cfg.gsc_service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)
        end_d = date.today()
        start_d = end_d - timedelta(days=days)

        request_body = {
            "startDate": start_d.isoformat(),
            "endDate": end_d.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": row_limit,
        }
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=request_body)
            .execute()
        )
        rows = response.get("rows", [])
        records = [
            {
                "query": r.get("keys", ["", ""])[0],
                "page": r.get("keys", ["", ""])[1],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": r.get("ctr", 0.0),
                "position": r.get("position", 0.0),
            }
            for r in rows
        ]
        df = pd.DataFrame(records)
        return classify_gsc_dataframe(df)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"GSC API error: {exc}",
            "summary": {},
            "dataframe": pd.DataFrame(),
        }
