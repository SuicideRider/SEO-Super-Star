"""SEO Super Star — Autonomous AI SEO Agent Server (`FastMCP`).

Exposes all 6 core SEO, GEO & AEO modules via the Model Context Protocol (MCP)
so Claude Desktop, Claude Code, Cursor, Gemini CLI, or custom Python agents can
invoke SEO Super Star tools natively without human copy-pasting.

Run locally or over HTTP:
    python mcp_server.py
"""

from typing import Any, Dict, List, Optional
from core.crawler_audit import audit_url_comprehensive, audit_xml_sitemap
from core.geo_aeo_schema import monitor_ai_citations, score_geo_aeo_readiness
from core.gsc_tracker import fetch_gsc_api_opportunities
from core.keyword_trends import expand_and_score_keywords
from core.serp_competitor import build_competitor_gap_brief
from core.storage import StorageManager

try:
    from fastmcp import FastMCP
    mcp = FastMCP("SEO Super Star — Autonomous SEO, GEO & AEO Agent Server")
except Exception:
    # Lightweight decorator shim if imported in an environment without fastmcp installed
    class _ShimMCP:
        def __init__(self, name: str):
            self.name = name
            self.tools = {}

        def tool(self):
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self):
            print(f"{self.name} initialized with tools: {list(self.tools.keys())}")

    mcp = _ShimMCP("SEO Super Star")


@mcp.tool()
def inspect_url_seo_and_geo(
    url: str,
    target_keyword: str = "",
    schema_type: str = "Article",
    run_pagespeed: bool = True,
) -> Dict[str, Any]:
    """Audit a webpage's technical SEO, DOM headings, links, CWV speed, and 0–100 GEO readiness score, and persist to DB."""
    audit = audit_url_comprehensive(url, run_pagespeed=run_pagespeed)
    geo = score_geo_aeo_readiness(
        audit,
        target_keyword=target_keyword or audit.get("title", {}).get("text", ""),
        schema_type=schema_type,
    )
    storage = StorageManager()
    record_id = storage.save_audit(
        audit,
        geo_score=geo["total_geo_score"],
        generated_jsonld=geo["generated_jsonld"],
    )
    return {
        "saved_audit_id": record_id,
        "technical_audit": audit,
        "geo_aeo_evaluation": geo,
    }


@mcp.tool()
def spider_xml_sitemap(sitemap_url: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Crawl an XML sitemap via advertools and return technical SEO diagnostics for up to `limit` URLs."""
    return audit_xml_sitemap(sitemap_url, limit=limit)


@mcp.tool()
def discover_keywords_and_trends(
    seed_keyword: str,
    country_code: str = "in",
    include_questions: bool = True,
    include_alphabet: bool = False,
) -> Dict[str, Any]:
    """Expand a seed keyword via keyless Google Autocomplete and score with trendspyg Google Trends momentum."""
    bundle = expand_and_score_keywords(
        seed=seed_keyword,
        gl=country_code,
        include_questions=include_questions,
        include_alphabet=include_alphabet,
    )
    StorageManager().save_keywords(seed_keyword, bundle.get("keywords", []))
    return bundle


@mcp.tool()
def reverse_engineer_serp_competitors(
    keyword: str,
    my_url: Optional[str] = None,
    max_competitors: int = 4,
) -> Dict[str, Any]:
    """Run the 3-tier free SERP waterfall (Tavily -> Gemini Grounding -> DDGS) and build a complete SEO/GEO content brief."""
    return build_competitor_gap_brief(
        keyword=keyword,
        my_url=my_url,
        max_competitors=max_competitors,
    )


@mcp.tool()
def check_brand_ai_citation_visibility(
    brand_name: str,
    domain: str,
    buyer_prompts: List[str],
) -> Dict[str, Any]:
    """Test a list of conversational buyer prompts to verify whether `brand_name` or `domain` is cited in AI answers."""
    return monitor_ai_citations(
        brand_name=brand_name,
        domain=domain,
        prompts=buyer_prompts,
    )


@mcp.tool()
def get_gsc_striking_distance_opportunities(
    site_url: str,
    days: int = 90,
    row_limit: int = 500,
) -> Dict[str, Any]:
    """Query Google Search Console API and return Striking Distance (Pos 4–15) and CTR Underperformer opportunities."""
    res = fetch_gsc_api_opportunities(site_url=site_url, days=days, row_limit=row_limit)
    df = res.get("dataframe")
    rows = df.head(50).to_dict(orient="records") if df is not None and not df.empty else []
    return {
        "status": res.get("status"),
        "summary": res.get("summary", {}),
        "top_opportunities": rows,
    }


@mcp.tool()
def log_seo_optimization_experiment(
    url: str,
    target_keyword: str,
    hypothesis: str,
    changes_made: str,
    baseline_position: float = 0.0,
    baseline_ctr: float = 0.0,
) -> Dict[str, Any]:
    """Record a page optimization change in the database so the AI agent can track ranking and CTR impact over time."""
    exp_id = StorageManager().log_experiment(
        url=url,
        target_keyword=target_keyword,
        hypothesis=hypothesis,
        changes_made=changes_made,
        baseline_position=baseline_position,
        baseline_ctr=baseline_ctr,
    )
    return {"status": "logged", "experiment_id": exp_id, "url": url}


if __name__ == "__main__":
    mcp.run()
