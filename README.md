# ⭐ SEO Super Star — 100% Free-Forever SEO, GEO & AEO Platform

**SEO Super Star** is a full-stack Python SEO, Generative Engine Optimization (GEO), and Answer Engine Optimization (AEO) platform designed for **both Human SEO Specialists** (via a 6-tab [Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud) dashboard) and **Autonomous AI SEO Agents** (via a [FastMCP](https://gofastmcp.com/docs/getting-started/welcome) Model Context Protocol server).

## 1. Quickstart (Run Locally in 60 Seconds)

```bash
pip install -r requirements.txt
streamlit run app.py
```

To launch the **AI SEO Agent MCP Server** (for Claude Desktop, Claude Code, Cursor, or custom Python agents):

```bash
python mcp_server.py
```

## 2. Deploy for $0 Forever on Streamlit Community Cloud

1. Push this folder to a free GitHub repository.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/), click **Create app**, select your repository, and set the main file path to `app.py`.
3. Under **Advanced settings -> Secrets**, paste any of your free keys from `.streamlit/secrets.toml.example` (Google AI Studio `GEMINI_API_KEY`, Groq `GROQ_API_KEY`, Tavily `TAVILY_API_KEY`, PageSpeed `PAGESPEED_API_KEY`, and Neon Serverless Postgres `DATABASE_URL`).
4. GitHub Actions will automatically run `.github/workflows/daily_seo_sync.yml` every morning to log fresh audits and rankings into your [Neon Serverless Postgres](https://neon.com/docs/introduction/plans) database.
