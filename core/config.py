"""Environment and configuration loader for SEO Super Star.

Supports loading from OS environment variables first, falling back to
Streamlit secrets (`st.secrets`) when running inside the Streamlit UI,
and degrading gracefully when zero API keys are configured.
"""

from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional


def _get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a secret from os.environ or streamlit.secrets safely."""
    val = os.environ.get(key)
    if val:
        return val.strip()
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            secret_val = st.secrets[key]
            if secret_val:
                return str(secret_val).strip()
    except Exception:
        pass
    return default


@dataclass
class Settings:
    """Centralized settings for SEO Super Star."""

    gemini_api_key: Optional[str] = field(
        default_factory=lambda: _get_secret("GEMINI_API_KEY")
    )
    gemini_models: List[str] = field(
        default_factory=lambda: [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
        ]
    )
    groq_api_key: Optional[str] = field(
        default_factory=lambda: _get_secret("GROQ_API_KEY")
    )
    groq_primary_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    tavily_api_key: Optional[str] = field(
        default_factory=lambda: _get_secret("TAVILY_API_KEY")
    )
    jina_api_key: Optional[str] = field(
        default_factory=lambda: _get_secret("JINA_API_KEY")
    )
    pagespeed_api_key: Optional[str] = field(
        default_factory=lambda: _get_secret("PAGESPEED_API_KEY")
    )
    database_url: str = field(
        default_factory=lambda: _get_secret(
            "DATABASE_URL", "sqlite:///seo_super_star.db"
        )
        or "sqlite:///seo_super_star.db"
    )
    gsc_service_account_json: Optional[str] = field(
        default_factory=lambda: _get_secret("GSC_SERVICE_ACCOUNT_JSON")
    )
    user_agent: str = (
        "Mozilla/5.0 (compatible; SEOSuperStarBot/1.0; +https://github.com/seo-super-star)"
    )

    def status_summary(self) -> Dict[str, Dict[str, str]]:
        """Return human-readable readiness status for each integration."""
        return {
            "Gemini Free API (Primary LLM + 5K Search Grounding)": {
                "configured": "Ready" if self.gemini_api_key else "Keyless Mode",
                "note": "Active" if self.gemini_api_key else "Set GEMINI_API_KEY for AI briefs & Google Search Grounding",
            },
            "Groq Free API (14,400 RPD Llama Failover)": {
                "configured": "Ready" if self.groq_api_key else "Keyless Mode",
                "note": "Active" if self.groq_api_key else "Set GROQ_API_KEY for automatic rate-limit failover",
            },
            "Tavily Search API (1,000 Free AI Searches/mo)": {
                "configured": "Ready" if self.tavily_api_key else "Using DDGS Fallback",
                "note": "Active" if self.tavily_api_key else "Falling back to keyless DuckDuckGo Search (ddgs)",
            },
            "Jina Reader API (JS-Rendered Markdown)": {
                "configured": "500 RPM Tier" if self.jina_api_key else "20 RPM Keyless Tier",
                "note": "Works without a key at 20 RPM; add JINA_API_KEY for 500 RPM",
            },
            "Google PageSpeed Insights API": {
                "configured": "25,000 RPD Key" if self.pagespeed_api_key else "Shared Public Quota",
                "note": "Works without a key for single checks; add PAGESPEED_API_KEY for bulk runs",
            },
            "Database Storage (Neon Postgres / SQLite)": {
                "configured": (
                    "Neon Serverless Postgres"
                    if self.database_url.startswith("postgres")
                    else "Local SQLite Fallback"
                ),
                "note": self.database_url.split("@")[-1] if "@" in self.database_url else self.database_url,
            },
            "Google Search Console API": {
                "configured": "Service Account Ready" if self.gsc_service_account_json else "CSV Dropzone Mode",
                "note": "Upload GSC CSV exports directly or add GSC_SERVICE_ACCOUNT_JSON",
            },
        }


def get_settings() -> Settings:
    """Return a fresh Settings instance reflecting current env/session overrides."""
    return Settings()
