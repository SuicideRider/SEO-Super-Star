"""Database & Google Sheets Persistence Layer for SEO Super Star.

Supports:
1. Neon Serverless Postgres (`postgresql://...`) via SQLAlchemy (`pool_pre_ping=True`)
   or `psycopg2` so scale-to-zero instances wake up transparently.
2. Built-in Python `sqlite3` fallback (`seo_super_star.db`) requiring zero external
   database packages for immediate local execution.
3. 1-click Google Sheets sync via `gspread`.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd
from core.config import Settings, get_settings


class StorageManager:
    """Manages Neon Serverless Postgres / SQLite persistence and Google Sheets export."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.db_url = self.settings.database_url
        self._use_postgres = self.db_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg2://"))
        self._sa_engine = None

        if self._use_postgres:
            try:
                from sqlalchemy import create_engine

                norm_url = self.db_url
                if norm_url.startswith("postgres://"):
                    norm_url = norm_url.replace("postgres://", "postgresql+psycopg2://", 1)
                elif norm_url.startswith("postgresql://") and "+psycopg2" not in norm_url:
                    norm_url = norm_url.replace("postgresql://", "postgresql+psycopg2://", 1)
                self._sa_engine = create_engine(norm_url, pool_pre_ping=True)
            except Exception:
                self._use_postgres = False

        self.sqlite_path = self._resolve_sqlite_path(self.db_url)
        self._init_schema()

    @staticmethod
    def _resolve_sqlite_path(db_url: str) -> str:
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "", 1)
        return "seo_super_star.db"

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create tables (`url_audits`, `keyword_clusters`, `seo_experiments`) if not present."""
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS url_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                audited_at TEXT NOT NULL,
                status_code INTEGER DEFAULT 200,
                title TEXT DEFAULT '',
                title_px INTEGER DEFAULT 0,
                meta_desc TEXT DEFAULT '',
                meta_px INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                h1_count INTEGER DEFAULT 0,
                missing_alt_count INTEGER DEFAULT 0,
                internal_links INTEGER DEFAULT 0,
                external_links INTEGER DEFAULT 0,
                seo_score REAL DEFAULT 0.0,
                performance_score REAL DEFAULT 0.0,
                geo_score REAL DEFAULT 0.0,
                schema_types TEXT DEFAULT '[]',
                generated_jsonld TEXT DEFAULT '',
                raw_audit_json TEXT DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS keyword_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed_keyword TEXT NOT NULL,
                keyword TEXT NOT NULL,
                modifier_type TEXT DEFAULT 'base',
                search_intent TEXT DEFAULT 'Informational',
                trend_score REAL DEFAULT 50.0,
                opportunity_score REAL DEFAULT 50.0,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS seo_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                target_keyword TEXT DEFAULT '',
                hypothesis TEXT DEFAULT '',
                changes_made TEXT DEFAULT '',
                baseline_position REAL DEFAULT 0.0,
                baseline_ctr REAL DEFAULT 0.0,
                current_position REAL DEFAULT 0.0,
                current_ctr REAL DEFAULT 0.0,
                status TEXT DEFAULT 'Active',
                created_at TEXT NOT NULL
            )
            """,
        ]

        if self._use_postgres and self._sa_engine is not None:
            from sqlalchemy import text

            pg_ddls = [
                stmt.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                for stmt in ddl_statements
            ]
            with self._sa_engine.begin() as conn:
                for stmt in pg_ddls:
                    conn.execute(text(stmt))
        else:
            with self._get_sqlite_conn() as conn:
                for stmt in ddl_statements:
                    conn.execute(stmt)
                conn.commit()

    def save_audit(
        self,
        audit_data: Dict[str, Any],
        geo_score: float = 0.0,
        generated_jsonld: str = "",
    ) -> int:
        """Persist a URL audit result and return its record ID."""
        ps = audit_data.get("pagespeed", {}) or {}
        headings = audit_data.get("headings", {}) or {}
        links = audit_data.get("links", {}) or {}
        images = audit_data.get("images", {}) or {}
        title_info = audit_data.get("title", {}) or {}
        meta_info = audit_data.get("meta_description", {}) or {}
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        params = (
            audit_data.get("final_url") or audit_data.get("url", ""),
            now_iso,
            int(audit_data.get("status_code", 0) or 0),
            str(title_info.get("text", ""))[:500],
            int(title_info.get("pixel_width", 0) or 0),
            str(meta_info.get("text", "")),
            int(meta_info.get("pixel_width", 0) or 0),
            int(audit_data.get("word_count", 0) or 0),
            len(headings.get("h1", []) or []),
            int(images.get("missing_alt_count", 0) or 0),
            int(links.get("internal_count", 0) or 0),
            int(links.get("external_count", 0) or 0),
            float(ps.get("seo_score", 0.0) or 0.0),
            float(ps.get("performance_score", 0.0) or 0.0),
            float(geo_score or 0.0),
            json.dumps(audit_data.get("schema_types", [])),
            generated_jsonld,
            json.dumps(audit_data, default=str),
        )

        if self._use_postgres and self._sa_engine is not None:
            from sqlalchemy import text

            with self._sa_engine.begin() as conn:
                res = conn.execute(
                    text(
                        """
                        INSERT INTO url_audits (
                            url, audited_at, status_code, title, title_px, meta_desc, meta_px,
                            word_count, h1_count, missing_alt_count, internal_links, external_links,
                            seo_score, performance_score, geo_score, schema_types, generated_jsonld, raw_audit_json
                        ) VALUES (
                            :u, :at, :sc, :t, :tpx, :md, :mpx, :wc, :h1, :alt, :il, :el,
                            :seo, :perf, :geo, :st, :jld, :raw
                        ) RETURNING id
                        """
                    ),
                    dict(
                        zip(
                            ["u", "at", "sc", "t", "tpx", "md", "mpx", "wc", "h1", "alt", "il", "el", "seo", "perf", "geo", "st", "jld", "raw"],
                            params,
                        )
                    ),
                )
                row = res.fetchone()
                return int(row[0]) if row else 1

        with self._get_sqlite_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO url_audits (
                    url, audited_at, status_code, title, title_px, meta_desc, meta_px,
                    word_count, h1_count, missing_alt_count, internal_links, external_links,
                    seo_score, performance_score, geo_score, schema_types, generated_jsonld, raw_audit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
            conn.commit()
            return int(cur.lastrowid or 1)

    def get_recent_audits(self, limit: int = 25) -> pd.DataFrame:
        """Return recent URL audits as a clean pandas DataFrame."""
        query = f"""
            SELECT id AS "ID", url AS "URL", audited_at AS "Audited At",
                   status_code AS "HTTP", word_count AS "Words", title_px AS "Title (px)",
                   h1_count AS "H1 Count", missing_alt_count AS "Missing Alts",
                   seo_score AS "Tech SEO Score", performance_score AS "CWV Speed Score",
                   geo_score AS "GEO Score"
            FROM url_audits
            ORDER BY id DESC
            LIMIT {int(limit)}
        """
        if self._use_postgres and self._sa_engine is not None:
            return pd.read_sql(query, self._sa_engine)
        with self._get_sqlite_conn() as conn:
            return pd.read_sql_query(query, conn)

    def save_keywords(self, seed: str, kw_rows: List[Dict[str, Any]]) -> int:
        """Persist a batch of enriched keyword rows."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if self._use_postgres and self._sa_engine is not None:
            from sqlalchemy import text

            with self._sa_engine.begin() as conn:
                for item in kw_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO keyword_clusters (
                                seed_keyword, keyword, modifier_type, search_intent,
                                trend_score, opportunity_score, created_at
                            ) VALUES (:s, :k, :m, :i, :t, :o, :c)
                            """
                        ),
                        {
                            "s": seed,
                            "k": str(item.get("keyword", "")),
                            "m": str(item.get("modifier_type", "base")),
                            "i": str(item.get("search_intent", "Informational")),
                            "t": float(item.get("trend_score", 50.0) or 50.0),
                            "o": float(item.get("opportunity_score", 50.0) or 50.0),
                            "c": now_iso,
                        },
                    )
            return len(kw_rows)

        with self._get_sqlite_conn() as conn:
            conn.executemany(
                """
                INSERT INTO keyword_clusters (
                    seed_keyword, keyword, modifier_type, search_intent,
                    trend_score, opportunity_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        seed,
                        str(item.get("keyword", "")),
                        str(item.get("modifier_type", "base")),
                        str(item.get("search_intent", "Informational")),
                        float(item.get("trend_score", 50.0) or 50.0),
                        float(item.get("opportunity_score", 50.0) or 50.0),
                        now_iso,
                    )
                    for item in kw_rows
                ],
            )
            conn.commit()
            return len(kw_rows)

    def log_experiment(
        self,
        url: str,
        target_keyword: str,
        hypothesis: str,
        changes_made: str,
        baseline_position: float = 0.0,
        baseline_ctr: float = 0.0,
    ) -> int:
        """Log a new SEO/GEO page optimization experiment."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._use_postgres and self._sa_engine is not None:
            from sqlalchemy import text

            with self._sa_engine.begin() as conn:
                res = conn.execute(
                    text(
                        """
                        INSERT INTO seo_experiments (
                            url, target_keyword, hypothesis, changes_made,
                            baseline_position, baseline_ctr, current_position, current_ctr, status, created_at
                        ) VALUES (:u, :k, :h, :c, :bp, :bc, :cp, :cc, 'Active', :dt)
                        RETURNING id
                        """
                    ),
                    {
                        "u": url,
                        "k": target_keyword,
                        "h": hypothesis,
                        "c": changes_made,
                        "bp": baseline_position,
                        "bc": baseline_ctr,
                        "cp": baseline_position,
                        "cc": baseline_ctr,
                        "dt": now_iso,
                    },
                )
                row = res.fetchone()
                return int(row[0]) if row else 1

        with self._get_sqlite_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO seo_experiments (
                    url, target_keyword, hypothesis, changes_made,
                    baseline_position, baseline_ctr, current_position, current_ctr, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
                """,
                (
                    url,
                    target_keyword,
                    hypothesis,
                    changes_made,
                    baseline_position,
                    baseline_ctr,
                    baseline_position,
                    baseline_ctr,
                    now_iso,
                ),
            )
            conn.commit()
            return int(cur.lastrowid or 1)

    def get_experiments(self) -> pd.DataFrame:
        """Fetch all logged SEO experiments."""
        query = """
            SELECT id AS "ID", created_at AS "Date", url AS "URL",
                   target_keyword AS "Keyword", hypothesis AS "Hypothesis",
                   changes_made AS "Changes Made", baseline_position AS "Base Pos",
                   ROUND(baseline_ctr * 100.0, 2) AS "Base CTR (%)",
                   current_position AS "Curr Pos",
                   ROUND(current_ctr * 100.0, 2) AS "Curr CTR (%)",
                   status AS "Status"
            FROM seo_experiments
            ORDER BY id DESC
        """
        if self._use_postgres and self._sa_engine is not None:
            return pd.read_sql(query, self._sa_engine)
        with self._get_sqlite_conn() as conn:
            return pd.read_sql_query(query, conn)

    def export_dataframe_to_gsheet(
        self,
        df: pd.DataFrame,
        spreadsheet_name: str,
        worksheet_name: str = "SEO_Super_Star",
    ) -> Dict[str, Any]:
        """Export any DataFrame to Google Sheets via gspread using Service Account JSON."""
        if not self.settings.gsc_service_account_json:
            return {
                "status": "missing_credentials",
                "message": "Add GSC_SERVICE_ACCOUNT_JSON to export directly to Google Sheets, or use the 1-click CSV download button.",
            }
        try:
            import gspread

            creds_dict = json.loads(self.settings.gsc_service_account_json)
            gc = gspread.service_account_from_dict(creds_dict)
            try:
                sh = gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                sh = gc.create(spreadsheet_name)

            try:
                ws = sh.worksheet(worksheet_name)
                ws.clear()
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=worksheet_name, rows="1000", cols="26")

            clean_df = df.fillna("").astype(str)
            ws.update([clean_df.columns.values.tolist()] + clean_df.values.tolist())
            return {
                "status": "ok",
                "spreadsheet_url": sh.url,
                "rows_written": len(clean_df),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
