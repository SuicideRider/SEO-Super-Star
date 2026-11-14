"""Module 4: 3-Tier Free SERP Waterfall & Competitor Content Gap Engine.

Executes a 100% free-forever SERP lookup waterfall:
1. Tavily Search API Free Researcher Tier (1,000 free AI searches/month, no credit card)
2. Google Gemini API Grounding with Google Search (5,000 free grounded prompts/month)
3. Keyless DuckDuckGo Search (`ddgs`) unlimited fallback

Then crawls top ranking pages via `crawler_audit.py` and generates a side-by-side
Entity Gap Matrix and SEO/GEO Content Brief.
"""

from collections import Counter
import re
from typing import Any, Dict, List, Optional
from core.config import Settings, get_settings
from core.crawler_audit import audit_url_comprehensive
from core.llm_router import DualLLMRouter


STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "your", "are", "was",
    "were", "have", "has", "had", "not", "but", "what", "all", "can", "when",
    "who", "will", "more", "about", "into", "than", "them", "then", "some",
    "how", "why", "which", "their", "there", "been", "also", "most", "other",
}


def search_serp_waterfall(
    query: str,
    max_results: int = 6,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Run the 3-tier free SERP waterfall (Tavily -> Gemini Search Grounding -> DDGS)."""
    cfg = settings or get_settings()

    # Tier 1: Tavily Free Researcher Plan (1,000 free credits/mo)
    if cfg.tavily_api_key:
        try:
            from tavily import TavilyClient

            t_client = TavilyClient(api_key=cfg.tavily_api_key)
            resp = t_client.search(
                query=query,
                search_depth="basic",
                include_answer=True,
                max_results=max_results,
            )
            items = [
                {
                    "position": idx + 1,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                }
                for idx, r in enumerate(resp.get("results", []))
                if r.get("url")
            ]
            if items:
                return {
                    "provider": "Tavily Free Researcher API",
                    "query": query,
                    "ai_overview_answer": resp.get("answer", ""),
                    "results": items,
                }
        except Exception:
            pass

    # Tier 2: Gemini Grounding with Google Search (5,000 free/mo)
    if cfg.gemini_api_key:
        router = DualLLMRouter(cfg)
        grounded = router.grounded_search(query)
        if grounded.get("status") == "ok" and grounded.get("citations"):
            items = [
                {
                    "position": idx + 1,
                    "title": c.get("title", ""),
                    "url": c.get("url", ""),
                    "snippet": "Cited in Google Search Grounding",
                }
                for idx, c in enumerate(grounded["citations"][:max_results])
            ]
            return {
                "provider": grounded.get("provider", "Gemini Search Grounding"),
                "query": query,
                "ai_overview_answer": grounded.get("answer", ""),
                "results": items,
            }

    # Tier 3: Keyless DuckDuckGo Search (`ddgs`)
    try:
        from ddgs import DDGS

        ddg_results = list(DDGS().text(query, max_results=max_results))
        items = [
            {
                "position": idx + 1,
                "title": r.get("title", ""),
                "url": r.get("href") or r.get("url", ""),
                "snippet": r.get("body") or r.get("snippet", ""),
            }
            for idx, r in enumerate(ddg_results)
            if (r.get("href") or r.get("url"))
        ]
        if items:
            return {
                "provider": "DuckDuckGo Keyless Search (ddgs)",
                "query": query,
                "ai_overview_answer": "",
                "results": items,
            }
    except Exception:
        pass

    return {
        "provider": "Offline Demo Fallback",
        "query": query,
        "ai_overview_answer": "",
        "results": [],
    }


def _extract_top_terms(markdown_text: str, top_n: int = 25) -> List[str]:
    """Extract frequent meaningful multi-character terms from page text."""
    tokens = re.findall(r"\b[a-zA-Z]{4,}\b", markdown_text.lower())
    filtered = [t for t in tokens if t not in STOPWORDS]
    counts = Counter(filtered)
    return [term for term, _ in counts.most_common(top_n)]


def build_competitor_gap_brief(
    keyword: str,
    my_url: Optional[str] = None,
    max_competitors: int = 4,
) -> Dict[str, Any]:
    """Scrape top SERP competitors, compare against `my_url`, and generate an SEO/GEO Brief."""
    serp_data = search_serp_waterfall(keyword, max_results=max_competitors + 2)
    competitor_rows: List[Dict[str, Any]] = []
    competitor_headings: List[str] = []
    term_counter: Counter = Counter()

    for item in serp_data.get("results", [])[:max_competitors]:
        comp_url = item.get("url", "")
        if not comp_url:
            continue
        audit = audit_url_comprehensive(comp_url, run_pagespeed=False)
        h2s = audit.get("headings", {}).get("h2", [])
        h3s = audit.get("headings", {}).get("h3", [])
        competitor_headings.extend(h2s + h3s)
        top_terms = _extract_top_terms(audit.get("rendered_markdown", ""), top_n=20)
        for t in set(top_terms):
            term_counter[t] += 1

        competitor_rows.append(
            {
                "position": item.get("position"),
                "url": comp_url,
                "title": audit.get("title", {}).get("text") or item.get("title", ""),
                "word_count": audit.get("word_count", 0),
                "h2_count": len(h2s),
                "h3_count": len(h3s),
                "schema_types": ", ".join(audit.get("schema_types", [])) or "None",
                "sample_h2s": h2s[:5],
            }
        )

    my_audit: Optional[Dict[str, Any]] = None
    my_terms = set()
    if my_url and my_url.strip():
        my_audit = audit_url_comprehensive(my_url.strip(), run_pagespeed=False)
        my_terms = set(_extract_top_terms(my_audit.get("rendered_markdown", ""), top_n=50))

    shared_competitor_entities = [
        term for term, freq in term_counter.most_common(20) if freq >= 2 or len(competitor_rows) <= 1
    ]
    missing_entities = [t for t in shared_competitor_entities if t not in my_terms]

    avg_words = (
        int(sum(c["word_count"] for c in competitor_rows if c["word_count"] > 0) / max(1, len(competitor_rows)))
        if competitor_rows
        else 1400
    )
    target_word_count = max(1200, int(avg_words * 1.15))

    router = DualLLMRouter()
    prompt = (
        f"Target Keyword: {keyword}\n"
        f"Competitor H2/H3 Headings Found: {competitor_headings[:25]}\n"
        f"High-Frequency Competitor Entities: {shared_competitor_entities}\n"
        f"Missing Entities on User Page ({my_url or 'New Page'}): {missing_entities}\n"
        f"Target Word Count: {target_word_count}\n\n"
        "Generate a comprehensive SEO & GEO Content Brief with:\n"
        "1. Recommended Title Tag (< 580px) & Meta Description (< 920px)\n"
        "2. A 50-word Direct Answer Block (for Google AI Overview / Perplexity citation)\n"
        "3. Complete H1-H3 Content Outline beating the competitors\n"
        "4. Top 4 People-Also-Ask FAQ questions with concise answers."
    )
    llm_brief = router.complete(prompt=prompt)

    return {
        "keyword": keyword,
        "serp_provider": serp_data.get("provider"),
        "ai_overview_answer": serp_data.get("ai_overview_answer", ""),
        "competitors": competitor_rows,
        "target_word_count": target_word_count,
        "shared_competitor_entities": shared_competitor_entities,
        "missing_entities": missing_entities,
        "my_url_audit": my_audit,
        "content_brief_markdown": llm_brief.get("content", ""),
        "llm_provider": f"{llm_brief.get('provider')} ({llm_brief.get('model')})",
    }
