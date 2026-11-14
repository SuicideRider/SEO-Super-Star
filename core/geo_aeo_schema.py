"""Module 5: GEO / AEO Readiness Scorer, AI Citation Tracker & Auto JSON-LD Schema Generator.

Scores any audited webpage from 0 to 100 on Generative Engine Optimization (GEO)
and Answer Engine Optimization (AEO) readiness across 4 pillars:
1. Direct Answer Block Presence (0–25 pts)
2. Entity & Quantitative Fact Density (0–25 pts)
3. Structural Scannability & Heading Clarity (0–25 pts)
4. Machine-Readable JSON-LD Schema Coverage (0–25 pts)

Also generates ready-to-paste, grounded JSON-LD (`FAQPage`, `Article`, `Product`,
`LocalBusiness`, `Organization`) and checks brand citation visibility across live AI search.
"""

import json
import re
from typing import Any, Dict, List
from core.llm_router import DualLLMRouter
from core.serp_competitor import search_serp_waterfall


def score_geo_aeo_readiness(
    audit_data: Dict[str, Any],
    target_keyword: str = "",
    schema_type: str = "Article",
) -> Dict[str, Any]:
    """Compute a 0–100 GEO/AEO Readiness Score and generate valid JSON-LD schema."""
    md_text = audit_data.get("rendered_markdown", "") or ""
    headings = audit_data.get("headings", {}) or {}
    h1s = headings.get("h1", [])
    h2s = headings.get("h2", [])
    h3s = headings.get("h3", [])
    word_count = int(audit_data.get("word_count", 0) or 0)
    existing_schemas = audit_data.get("schema_types", []) or []

    # 1. Direct Answer Block Score (0-25)
    question_headings = [
        h for h in (h2s + h3s)
        if "?" in h or h.lower().startswith(("what ", "how ", "why ", "when ", "which ", "is ", "can "))
    ]
    paragraphs = [p.strip() for p in md_text.split("\n\n") if 35 <= len(p.split()) <= 75]
    answer_block_score = min(
        25.0,
        (min(3, len(question_headings)) * 5.0) + (min(2, len(paragraphs)) * 5.0),
    )

    # 2. Quantitative Fact & Entity Density Score (0-25)
    numeric_facts = re.findall(r"\b\d+(?:\.\d+)?(?:\s*%|\s*x|\s*kg|\s*ms|\s*gb|\s*years?|\s*months?|\s*days?)?\b", md_text.lower())
    outbound_links = int(audit_data.get("links", {}).get("external_count", 0) or 0)
    fact_density = (len(numeric_facts) / max(1, word_count)) * 1000
    entity_fact_score = min(
        25.0,
        round(min(15.0, fact_density * 0.8) + min(10.0, outbound_links * 2.0), 1),
    )

    # 3. Structural Scannability Score (0-25)
    has_single_h1 = 10.0 if len(h1s) == 1 else (4.0 if len(h1s) > 1 else 0.0)
    h2_depth_pts = min(10.0, len(h2s) * 2.5)
    bullet_lines = len(re.findall(r"^\s*[-*•]\s+", md_text, flags=re.M))
    list_pts = 5.0 if bullet_lines >= 3 else (2.5 if bullet_lines >= 1 else 0.0)
    structure_score = round(min(25.0, has_single_h1 + h2_depth_pts + list_pts), 1)

    # 4. Schema Coverage Score (0-25)
    if len(existing_schemas) >= 2:
        schema_score = 25.0
    elif len(existing_schemas) == 1:
        schema_score = 16.0
    else:
        schema_score = 0.0

    total_geo_score = round(
        answer_block_score + entity_fact_score + structure_score + schema_score, 1
    )

    recommendations: List[str] = []
    if answer_block_score < 18:
        recommendations.append(
            "Add 2–3 question-phrased H2/H3 subheadings immediately followed by a self-contained 45–60 word direct answer paragraph so AI Overviews and Perplexity can quote your page verbatim."
        )
    if entity_fact_score < 18:
        recommendations.append(
            "Increase citation & statistic density: add concrete numbers, benchmarks, or outbound links to primary documentation."
        )
    if structure_score < 18:
        recommendations.append(
            "Ensure exactly 1 H1 tag, at least 4 descriptive H2 headings, and bulleted summary lists for LLM chunking."
        )
    if schema_score < 20:
        recommendations.append(
            f"Embed the generated `{schema_type}` and `FAQPage` JSON-LD script in your page `<head>` to explicitly declare entities to search engines."
        )

    generated_jsonld = generate_grounded_jsonld(
        audit_data=audit_data,
        target_keyword=target_keyword,
        schema_type=schema_type,
    )

    return {
        "url": audit_data.get("final_url") or audit_data.get("url", ""),
        "target_keyword": target_keyword,
        "total_geo_score": total_geo_score,
        "breakdown": {
            "direct_answer_blocks_25": answer_block_score,
            "fact_and_citation_density_25": entity_fact_score,
            "structural_scannability_25": structure_score,
            "schema_coverage_25": schema_score,
        },
        "question_headings_found": question_headings,
        "recommendations": recommendations,
        "generated_jsonld": generated_jsonld,
    }


def generate_grounded_jsonld(
    audit_data: Dict[str, Any],
    target_keyword: str = "",
    schema_type: str = "Article",
) -> str:
    """Build valid, grounded JSON-LD markup from extracted page metadata."""
    url = audit_data.get("final_url") or audit_data.get("url", "https://example.com")
    title = audit_data.get("title", {}).get("text") or target_keyword or "Web Page"
    desc = audit_data.get("meta_description", {}).get("text") or f"Comprehensive guide on {title}."
    h2s = audit_data.get("headings", {}).get("h2", [])[:5]

    base_graph: List[Dict[str, Any]] = [
        {
            "@type": schema_type,
            "@id": f"{url}#{schema_type.lower()}",
            "headline": title[:110],
            "name": title,
            "description": desc,
            "url": url,
            "keywords": target_keyword or title,
        }
    ]

    if h2s:
        faq_entities = [
            {
                "@type": "Question",
                "name": h if h.endswith("?") else f"What should you know about {h}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"See our detailed section on {h} at {url}.",
                },
            }
            for h in h2s[:4]
        ]
        base_graph.append(
            {
                "@type": "FAQPage",
                "@id": f"{url}#faq",
                "mainEntity": faq_entities,
            }
        )

    schema_obj = {
        "@context": "https://schema.org",
        "@graph": base_graph,
    }
    return json.dumps(schema_obj, indent=2)


def monitor_ai_citations(
    brand_name: str,
    domain: str,
    prompts: List[str],
) -> Dict[str, Any]:
    """Check whether `brand_name` or `domain` is cited across target buyer prompts."""
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
    brand_lower = brand_name.lower().strip()
    rows: List[Dict[str, Any]] = []
    router = DualLLMRouter()

    cited_count = 0
    for prompt_q in prompts:
        q_str = prompt_q.strip()
        if not q_str:
            continue
        grounded = router.grounded_search(q_str)
        if grounded.get("status") == "ok" and (grounded.get("answer") or grounded.get("citations")):
            answer_text = grounded.get("answer", "")
            citations = grounded.get("citations", [])
            provider_used = grounded.get("provider", "Gemini Search Grounding")
        else:
            serp = search_serp_waterfall(q_str, max_results=6)
            answer_text = serp.get("ai_overview_answer", "")
            citations = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")}
                for r in serp.get("results", [])
            ]
            provider_used = serp.get("provider", "SERP Waterfall")

        combined_blob = (
            answer_text.lower()
            + " "
            + " ".join(
                f"{c.get('title', '')} {c.get('url', '')} {c.get('snippet', '')}".lower()
                for c in citations
            )
        )
        brand_mentioned = bool(brand_lower and brand_lower in combined_blob)
        domain_cited = any(clean_domain in (c.get("url", "").lower()) for c in citations if clean_domain)
        is_visible = brand_mentioned or domain_cited
        if is_visible:
            cited_count += 1

        top_competitor_urls = [c.get("url", "") for c in citations[:3] if c.get("url")]
        rows.append(
            {
                "prompt": q_str,
                "provider": provider_used,
                "brand_mentioned": "Yes" if brand_mentioned else "No",
                "domain_cited_in_sources": "Yes" if domain_cited else "No",
                "visibility_status": "Cited / Visible" if is_visible else "Citation Gap",
                "top_cited_sources": ", ".join(top_competitor_urls),
            }
        )

    total_checked = max(1, len(rows))
    visibility_pct = round((cited_count / total_checked) * 100, 1)
    return {
        "brand_name": brand_name,
        "domain": clean_domain,
        "prompts_tested": len(rows),
        "visibility_score_pct": visibility_pct,
        "results": rows,
    }
