# IMDB Explorer

A full-stack application that provides a **graph analytic interface** and **instant data querying** over the IMDB dataset. Explore relationships between titles, people, and roles through a Neo4j-powered graph layer, or run fast relational queries via DuckDB — all served through a REST API to a React front-end.

## Architecture

```
IMDB TSV.GZ → Parquet → DuckDB ──→ FastAPI → React + Vite
                           ↓
                         Neo4j (graph analytics)
```

| Layer | Technology |
|---|---|
| Relational store | DuckDB (Parquet files) |
| Graph store | Neo4j |
| API | FastAPI + Granian |
| Front-end | React 19 · TypeScript · Vite · Tailwind CSS · shadcn/ui |

## Quick Start

```bash
# 1. Start infrastructure (Neo4j Docker container)
make install

# 2. Seed data — downloads IMDB, builds Parquet, loads DuckDB & Neo4j
make seed-sample   # ~1,000 titles, fast (dev/testing)
# make seed        # full dataset (~30 min, ~1.5 GB download)

# 3. Start all dev servers
make dev
```

The React app runs at `http://localhost:3000`; the API at `http://localhost:8000`.
