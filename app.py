"""SEO Super Star — 6-Tab Streamlit Human SEO, GEO & AEO Cockpit.

Deployable for $0 forever on Streamlit Community Cloud (`share.streamlit.io`).
Works immediately with zero API keys configured, and unlocks Gemini Search Grounding,
Groq 14,400 RPD failover, Tavily AI SERP, PageSpeed 25,000 RPD, Neon Serverless Postgres,
and Google Search Console API as keys are added in `.streamlit/secrets.toml` or the sidebar.
"""

import json
import os
import pandas as pd
import streamlit as st

from core.config import get_settings
from core.crawler_audit import audit_url_comprehensive, audit_xml_sitemap
from core.geo_aeo_schema import monitor_ai_citations, score_geo_aeo_readiness
from core.gsc_tracker import classify_gsc_dataframe, fetch_gsc_api_opportunities
from core.keyword_trends import expand_and_score_keywords
from core.serp_competitor import build_competitor_gap_brief
from core.storage import StorageManager

st.set_page_config(
    page_title="SEO Super Star — Free-Forever SEO, GEO & AEO Suite",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar: Runtime Free API Key Configuration & Integration Readiness
with st.sidebar:
    st.title("⭐ SEO Super Star")
    st.caption("100% Free-Forever Human + AI Agent SEO, GEO & AEO Suite")

    with st.expander("🔑 Configure Free API Keys (Optional)", expanded=False):
        st.markdown(
            "All core tools work **keyless** out of the box. Paste free keys below or in `.streamlit/secrets.toml` to unlock higher quotas:"
        )
        gemini_in = st.text_input(
            "Gemini API Key (Google AI Studio)",
            value=os.environ.get("GEMINI_API_KEY", ""),
            type="password",
        )
        groq_in = st.text_input(
            "Groq API Key (14.4K RPD Failover)",
            value=os.environ.get("GROQ_API_KEY", ""),
            type="password",
        )
        tavily_in = st.text_input(
            "Tavily API Key (1,000/mo Free SERP)",
            value=os.environ.get("TAVILY_API_KEY", ""),
            type="password",
        )
        jina_in = st.text_input(
            "Jina Reader Key (500 RPM JS Reader)",
            value=os.environ.get("JINA_API_KEY", ""),
            type="password",
        )
        psi_in = st.text_input(
            "PageSpeed API Key (25K/day Quota)",
            value=os.environ.get("PAGESPEED_API_KEY", ""),
            type="password",
        )
        db_in = st.text_input(
            "Neon Postgres DATABASE_URL",
            value=os.environ.get("DATABASE_URL", ""),
            type="password",
        )

        if st.button("Apply Runtime Keys", use_container_width=True):
            if gemini_in:
                os.environ["GEMINI_API_KEY"] = gemini_in.strip()
            if groq_in:
                os.environ["GROQ_API_KEY"] = groq_in.strip()
            if tavily_in:
                os.environ["TAVILY_API_KEY"] = tavily_in.strip()
            if jina_in:
                os.environ["JINA_API_KEY"] = jina_in.strip()
            if psi_in:
                os.environ["PAGESPEED_API_KEY"] = psi_in.strip()
            if db_in:
                os.environ["DATABASE_URL"] = db_in.strip()
            st.success("Runtime keys updated!")

    settings = get_settings()
    storage = StorageManager(settings)

    st.subheader("📡 System & Quota Status")
    for service_name, info in settings.status_summary().items():
        st.markdown(f"**{service_name}**  \n`{info['configured']}` — _{info['note']}_")

st.title("⭐ SEO Super Star — Free-Forever SEO, GEO & AEO Platform")
st.markdown(
    "Unified cockpit for **Technical SEO**, **Google Autocomplete + `trendspyg` Keyword Discovery**, "
    "**3-Tier Competitor SERP Gap Briefs**, **GEO/AEO Citation & Schema Generation**, and **Google Search Console Opportunity Mining**."
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "1️⃣ Technical & CWV Auditor",
        "2️⃣ Keyword & Trends Scorer",
        "3️⃣ Competitor SERP & Content Brief",
        "4️⃣ GEO / AEO & Schema Generator",
        "5️⃣ GSC Opportunity Miner",
        "6️⃣ Experiments & DB / GSheets Sync",
    ]
)

# ==============================================================================
# TAB 1: ON-PAGE, SITEMAP & CORE WEB VITALS AUDITOR
# ==============================================================================
with tab1:
    st.subheader("Technical SEO, JS-Rendered DOM & Core Web Vitals Auditor")
    audit_mode = st.radio(
        "Select Audit Mode",
        ["Single URL Deep Audit", "XML Sitemap Batch Spider (advertools)"],
        horizontal=True,
    )

    if audit_mode == "Single URL Deep Audit":
        col_u1, col_u2 = st.columns([3, 1])
        with col_u1:
            target_url = st.text_input(
                "Enter Page URL to Audit",
                value="https://example.com",
                placeholder="https://yourdomain.com/product-page",
            )
        with col_u2:
            run_psi = st.checkbox("Run PageSpeed CWV API", value=True)
            schema_choice = st.selectbox(
                "Target Schema Type",
                ["Article", "Product", "LocalBusiness", "Organization"],
            )

        if st.button("🚀 Run Comprehensive Technical & GEO Audit", type="primary"):
            with st.spinner(f"Auditing {target_url} via BeautifulSoup4, Jina Reader, and PageSpeed API..."):
                audit_res = audit_url_comprehensive(target_url, run_pagespeed=run_psi)
                geo_res = score_geo_aeo_readiness(
                    audit_res,
                    target_keyword=audit_res.get("title", {}).get("text", ""),
                    schema_type=schema_choice,
                )
                storage.save_audit(
                    audit_res,
                    geo_score=geo_res["total_geo_score"],
                    generated_jsonld=geo_res["generated_jsonld"],
                )
                st.session_state["last_audit"] = audit_res
                st.session_state["last_geo"] = geo_res

        if "last_audit" in st.session_state:
            a = st.session_state["last_audit"]
            g = st.session_state["last_geo"]
            ps = a.get("pagespeed", {}) or {}

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("HTTP Status", a.get("status_code", 0), f"{a.get('response_time_ms', 0)} ms")
            m2.metric("Word Count", a.get("word_count", 0), a.get("extractor_used", ""))
            m3.metric("Lighthouse SEO", f"{ps.get('seo_score', 0)}/100", f"LCP: {ps.get('lcp_display', 'N/A')}")
            m4.metric("CWV Speed Score", f"{ps.get('performance_score', 0)}/100", f"CLS: {ps.get('cls_display', 'N/A')}")
            m5.metric("GEO / AEO Readiness", f"{g.get('total_geo_score', 0)}/100", f"{len(a.get('schema_types', []))} Schemas")

            if a.get("issues"):
                st.warning("**Actionable Technical & On-Page Issues Detected:**\n- " + "\n- ".join(a["issues"]))
            else:
                st.success("Zero critical technical or metadata issues detected!")

            c_left, c_right = st.columns(2)
            with c_left:
                st.markdown("#### Metadata & SERP Pixel Checks")
                st.json(
                    {
                        "Title Tag": a.get("title"),
                        "Meta Description": a.get("meta_description"),
                        "Canonical URL": a.get("canonical_url"),
                        "Robots Directive": a.get("robots_meta"),
                        "Detected JSON-LD Types": a.get("schema_types"),
                    }
                )
            with c_right:
                st.markdown("#### Heading Hierarchy (`H1`–`H6`) & Link Graph")
                st.json(
                    {
                        "H1 Headings": a.get("headings", {}).get("h1", []),
                        "H2 Headings": a.get("headings", {}).get("h2", [])[:10],
                        "H3 Headings": a.get("headings", {}).get("h3", [])[:10],
                        "Link Summary": a.get("links", {}),
                        "Image Alt Summary": a.get("images", {}),
                    }
                )

            with st.expander("📄 View Extracted JS-Rendered Markdown (Jina Reader / Trafilatura)"):
                st.code(a.get("rendered_markdown", "")[:4000], language="markdown")

    else:
        sitemap_url = st.text_input(
            "Enter XML Sitemap URL",
            placeholder="https://yourdomain.com/sitemap.xml",
        )
        max_urls = st.slider("Max URLs to Crawl in Batch", min_value=5, max_value=50, value=15)
        if st.button("🕷️ Crawl XML Sitemap", type="primary") and sitemap_url:
            with st.spinner(f"Parsing sitemap and auditing up to {max_urls} URLs..."):
                batch_results = audit_xml_sitemap(sitemap_url, limit=max_urls)
                for item in batch_results:
                    geo_eval = score_geo_aeo_readiness(item)
                    storage.save_audit(item, geo_score=geo_eval["total_geo_score"], generated_jsonld=geo_eval["generated_jsonld"])
                batch_df = pd.DataFrame(
                    [
                        {
                            "URL": r.get("final_url"),
                            "HTTP": r.get("status_code"),
                            "Title": r.get("title", {}).get("text", ""),
                            "Title Px": r.get("title", {}).get("pixel_width", 0),
                            "Words": r.get("word_count", 0),
                            "H1s": len(r.get("headings", {}).get("h1", [])),
                            "Missing Alts": r.get("images", {}).get("missing_alt_count", 0),
                            "Schemas": ", ".join(r.get("schema_types", [])),
                            "Issues": len(r.get("issues", [])),
                        }
                        for r in batch_results
                    ]
                )
                st.dataframe(batch_df, use_container_width=True)
                st.download_button(
                    "⬇️ Download Sitemap Audit CSV",
                    data=batch_df.to_csv(index=False).encode("utf-8"),
                    file_name="seo_super_star_sitemap_audit.csv",
                    mime="text/csv",
                )

# ==============================================================================
# TAB 2: KEYWORD AUTOCOMPLETE EXPANDER & GOOGLE TRENDS (TRENDSPYG) SCORER
# ==============================================================================
with tab2:
    st.subheader("Zero-Cost Keyword Discovery (`suggestqueries.google.com`) + `trendspyg` Velocity")
    k_col1, k_col2, k_col3, k_col4 = st.columns([3, 1, 1, 1])
    with k_col1:
        seed_kw = st.text_input(
            "Enter Seed Keyword or Product Topic",
            value="wood pressed oil",
            placeholder="e.g., cold pressed groundnut oil, AI SEO agency",
        )
    with k_col2:
        country_code = st.selectbox("Target Country (gl)", ["in", "us", "gb", "ae", "sg", "au"], index=0)
    with k_col3:
        inc_q = st.checkbox("Question Modifiers", value=True)
    with k_col4:
        inc_alpha = st.checkbox("A–Z Alphabet Soup", value=False)

    if st.button("🔍 Expand Keywords & Score Opportunity", type="primary"):
        with st.spinner(f"Querying Google Autocomplete & trendspyg for '{seed_kw}'..."):
            kw_bundle = expand_and_score_keywords(
                seed=seed_kw,
                gl=country_code,
                include_questions=inc_q,
                include_alphabet=inc_alpha,
            )
            storage.save_keywords(seed_kw, kw_bundle["keywords"])
            st.session_state["kw_bundle"] = kw_bundle

    if "kw_bundle" in st.session_state:
        kb = st.session_state["kw_bundle"]
        t_info = kb.get("trend_summary", {})
        kc1, kc2, kc3 = st.columns(3)
        kc1.metric("Total Keywords Discovered", kb.get("total_keywords", 0))
        kc2.metric("Google Trends Index (0–100)", t_info.get("current_interest_index", 65.0), t_info.get("direction", "Steady"))
        kc3.metric("Trend Data Source", t_info.get("source", "trendspyg"))

        kw_df = pd.DataFrame(kb.get("keywords", []))
        st.dataframe(kw_df, use_container_width=True)
        st.download_button(
            "⬇️ Download Keyword Opportunity Matrix (CSV)",
            data=kw_df.to_csv(index=False).encode("utf-8"),
            file_name=f"keywords_{seed_kw.replace(' ', '_')}.csv",
            mime="text/csv",
        )

# ==============================================================================
# TAB 3: LIVE SERP COMPETITOR GAP & CONTENT BRIEF BUILDER
# ==============================================================================
with tab3:
    st.subheader("3-Tier Free SERP Waterfall (`Tavily` → `Gemini Grounding` → `ddgs`) & Content Brief")
    s_col1, s_col2 = st.columns([2, 2])
    with s_col1:
        serp_kw = st.text_input(
            "Target Keyword to Rank For",
            value="wood pressed sesame oil benefits",
        )
    with s_col2:
        my_page_url = st.text_input(
            "Your Existing Page URL (Optional — for Entity Gap Comparison)",
            value="",
            placeholder="https://yourdomain.com/sesame-oil",
        )

    if st.button("📊 Reverse-Engineer Top Competitors & Build Brief", type="primary"):
        with st.spinner(f"Running 3-tier SERP waterfall and auditing top competitors for '{serp_kw}'..."):
            brief_data = build_competitor_gap_brief(serp_kw, my_url=my_page_url or None)
            st.session_state["brief_data"] = brief_data

    if "brief_data" in st.session_state:
        bd = st.session_state["brief_data"]
        b1, b2, b3 = st.columns(3)
        b1.metric("SERP Waterfall Source", bd.get("serp_provider", "N/A"))
        b2.metric("Recommended Word Count", f"{bd.get('target_word_count', 1400)} words")
        b3.metric("AI Synthesis Engine", bd.get("llm_provider", "Local Engine"))

        if bd.get("ai_overview_answer"):
            st.info(f"**Live AI Answer / Overview Snapshot:**\n\n{bd['ai_overview_answer']}")

        if bd.get("competitors"):
            st.markdown("#### Top Organic Competitors Analyzed")
            st.dataframe(pd.DataFrame(bd["competitors"]), use_container_width=True)

        col_ent1, col_ent2 = st.columns(2)
        with col_ent1:
            st.markdown("#### Core Entities Across Top Competitors")
            st.write(", ".join(bd.get("shared_competitor_entities", [])) or "Run with live SERP connection")
        with col_ent2:
            st.markdown("#### Missing Entities on Your Page")
            st.write(", ".join(bd.get("missing_entities", [])) or "None")

        st.markdown("#### Generated SEO & GEO Content Brief")
        st.markdown(bd.get("content_brief_markdown", ""))

# ==============================================================================
# TAB 4: GEO / AEO CITATION SCORER & AUTO JSON-LD SCHEMA GENERATOR
# ==============================================================================
with tab4:
    st.subheader("GEO / AEO Citation Visibility Monitor & Grounded JSON-LD Generator")
    g_col1, g_col2 = st.columns(2)

    with g_col1:
        st.markdown("#### 1. Multi-Prompt AI Citation Tracker")
        brand_in = st.text_input("Your Brand Name", value="Village Mill")
        domain_in = st.text_input("Your Domain", value="villagemill.in")
        prompts_in = st.text_area(
            "Buyer Prompts to Test (1 per line)",
            value="best wood pressed cooking oil brand in Coimbatore\npure cold pressed sesame oil in Tamil Nadu\nwood pressed groundnut oil vs refined oil for heart health",
            height=120,
        )
        if st.button("🤖 Check AI Search Citation Visibility", type="primary"):
            prompt_list = [p.strip() for p in prompts_in.splitlines() if p.strip()]
            with st.spinner("Testing buyer prompts across Gemini Search Grounding / Tavily / DDGS..."):
                cit_report = monitor_ai_citations(brand_in, domain_in, prompt_list)
                st.session_state["cit_report"] = cit_report

        if "cit_report" in st.session_state:
            cr = st.session_state["cit_report"]
            st.metric(
                "AI Citation Visibility Score",
                f"{cr.get('visibility_score_pct', 0)}%",
                f"{cr.get('prompts_tested', 0)} buyer prompts tested",
            )
            st.dataframe(pd.DataFrame(cr.get("results", [])), use_container_width=True)

    with g_col2:
        st.markdown("#### 2. Grounded JSON-LD Schema Generator")
        if "last_geo" in st.session_state:
            lg = st.session_state["last_geo"]
            st.metric("Latest Audited URL GEO Score", f"{lg.get('total_geo_score', 0)} / 100")
            st.json(lg.get("breakdown", {}))
            for rec in lg.get("recommendations", []):
                st.markdown(f"- {rec}")
            st.markdown("##### Ready-to-Paste `<script type=\"application/ld+json\">`")
            st.code(
                f'<script type="application/ld+json">\n{lg.get("generated_jsonld", "")}\n</script>',
                language="html",
            )
        else:
            st.info("Run a Single URL Audit in Tab 1 to auto-score GEO readiness and generate grounded JSON-LD schema.")

# ==============================================================================
# TAB 5: GOOGLE SEARCH CONSOLE OPPORTUNITY MINER (API + CSV DROPZONE)
# ==============================================================================
with tab5:
    st.subheader("Google Search Console Opportunity Miner (Striking Distance & CTR Fixes)")
    gsc_mode = st.radio(
        "Data Source",
        [
            "Upload GSC Export CSV (Zero Setup)",
            "Load Built-In Sample GSC Dataset (Instant Demo)",
            "Connect Live Google Search Console API (Service Account)",
        ],
        horizontal=True,
    )

    gsc_result = None
    if gsc_mode == "Upload GSC Export CSV (Zero Setup)":
        uploaded_csv = st.file_uploader("Upload Queries or Pages CSV from Google Search Console", type=["csv"])
        if uploaded_csv is not None:
            raw_df = pd.read_csv(uploaded_csv)
            gsc_result = classify_gsc_dataframe(raw_df)

    elif gsc_mode == "Load Built-In Sample GSC Dataset (Instant Demo)":
        if st.button("📈 Run Opportunity Miner on Sample GSC Data", type="primary"):
            sample_df = pd.DataFrame(
                [
                    {"query": "wood pressed groundnut oil coimbatore", "page": "/groundnut-oil", "clicks": 48, "impressions": 1420, "ctr": "3.38%", "position": 6.4},
                    {"query": "cold pressed sesame oil 1 litre price", "page": "/sesame-oil", "clicks": 31, "impressions": 1890, "ctr": "1.64%", "position": 4.2},
                    {"query": "best mara chekku oil in tamil nadu", "page": "/about-village-mill", "clicks": 19, "impressions": 980, "ctr": "1.94%", "position": 9.8},
                    {"query": "pure coconut oil for cooking", "page": "/coconut-oil", "clicks": 12, "impressions": 1150, "ctr": "1.04%", "position": 18.5},
                    {"query": "ai seo agency india", "page": "/geo-aeo-services", "clicks": 25, "impressions": 860, "ctr": "2.91%", "position": 7.1},
                    {"query": "village mill cooking oil", "page": "/", "clicks": 210, "impressions": 620, "ctr": "33.87%", "position": 1.2},
                ]
            )
            gsc_result = classify_gsc_dataframe(sample_df)

    else:
        gsc_site = st.text_input("GSC Property URL", placeholder="sc-domain:yourdomain.com or https://yourdomain.com/")
        gsc_days = st.slider("Lookback Window (Days)", 7, 180, 90)
        if st.button("🔄 Pull Live GSC API Data", type="primary") and gsc_site:
            gsc_result = fetch_gsc_api_opportunities(gsc_site, days=gsc_days)
            if gsc_result.get("status") != "ok":
                st.warning(gsc_result.get("message", "Unable to fetch GSC API."))

    if gsc_result and gsc_result.get("status") == "ok":
        s = gsc_result["summary"]
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Striking Distance (Pos 4–15)", s.get("striking_distance_count", 0))
        g2.metric("CTR Underperformers (Pos 1–5)", s.get("ctr_underperformer_count", 0))
        g3.metric("Cluster Expansion (Pos 16–35)", s.get("cluster_expansion_count", 0))
        g4.metric("Top Winners (Pos 1–3)", s.get("top_winner_count", 0))

        out_df = gsc_result["dataframe"]
        st.dataframe(out_df, use_container_width=True)
        st.download_button(
            "⬇️ Download Prioritized GSC Action Plan (CSV)",
            data=out_df.to_csv(index=False).encode("utf-8"),
            file_name="seo_super_star_gsc_opportunities.csv",
            mime="text/csv",
        )

# ==============================================================================
# TAB 6: SEO EXPERIMENT TRACKER & NEON DB / GOOGLE SHEETS SYNC
# ==============================================================================
with tab6:
    st.subheader("Closed-Loop SEO Experiment Tracker & Cloud Database History")
    col_e1, col_e2 = st.columns([1, 2])

    with col_e1:
        st.markdown("#### Log New Optimization Experiment")
        exp_url = st.text_input("Optimized Page URL", value="https://villagemill.in/groundnut-oil")
        exp_kw = st.text_input("Target Keyword", value="wood pressed groundnut oil coimbatore")
        exp_hyp = st.text_input("Hypothesis", value="Adding 50-word answer block + FAQPage schema will lift Pos 6.4 -> Top 3")
        exp_chg = st.text_area("Changes Made", value="Updated Title pixel width to 510px, added H2 question + JSON-LD FAQPage")
        exp_pos = st.number_input("Baseline Average Position", value=6.4, step=0.1)
        exp_ctr = st.number_input("Baseline CTR (0.034 = 3.4%)", value=0.034, step=0.005, format="%.3f")

        if st.button("💾 Save Experiment to Database", type="primary"):
            exp_id = storage.log_experiment(
                url=exp_url,
                target_keyword=exp_kw,
                hypothesis=exp_hyp,
                changes_made=exp_chg,
                baseline_position=exp_pos,
                baseline_ctr=exp_ctr,
            )
            st.success(f"Logged SEO Experiment #{exp_id}!")

    with col_e2:
        st.markdown("#### Logged SEO Experiments (`seo_experiments` table)")
        exp_df = storage.get_experiments()
        st.dataframe(exp_df, use_container_width=True)

        st.markdown("#### Recent URL Audits Stored in Database (`url_audits` table)")
        audits_df = storage.get_recent_audits(limit=25)
        st.dataframe(audits_df, use_container_width=True)

        sheet_title = st.text_input("Google Sheet Name for `gspread` Sync", value="SEO_Super_Star_Master_Tracker")
        if st.button("📤 Sync Audit History to Google Sheets"):
            sync_res = storage.export_dataframe_to_gsheet(audits_df, spreadsheet_name=sheet_title)
            if sync_res.get("status") == "ok":
                st.success(f"Synced {sync_res.get('rows_written')} rows! Open: {sync_res.get('spreadsheet_url')}")
            else:
                st.info(sync_res.get("message"))
