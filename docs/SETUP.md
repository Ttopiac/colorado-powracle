# Full Setup Guide

## API Keys

You need three API keys. All have free tiers sufficient for personal use.

| Service | Purpose | Sign up at |
|---------|---------|-----------|
| **OpenRouter** | Routes requests to the Claude 3 Haiku LLM | [openrouter.ai](https://openrouter.ai) → Keys → Create Key |
| **SerpAPI** | Live Google search (lift status, road conditions) | [serpapi.com](https://serpapi.com) → Dashboard → API Key |
| **COtrip** | Live Colorado road conditions & chain laws (optional) | [manage-api.cotrip.org](https://manage-api.cotrip.org/login) → Register → My Account → API Key |

> COtrip is optional — if omitted, road condition questions fall back to web search automatically.

Create a `.env` file in the project root (gitignored — never commit it):

```
OPENROUTER_API_KEY=sk-or-your-key-here
SERPAPI_API_KEY=your-serpapi-key-here
COTRIP_API_KEY=your-cotrip-key-here

# PostgreSQL for user accounts (see below)
# DATABASE_URL=postgresql://powracle_user:your_secure_password@localhost:5432/powracle
```

## Data Ingestion

Download historical data and build the local database. Run once.

```bash
conda activate powracle

# 10 years of daily SNOTEL readings (~3 MB, ~2 min)
PYTHONPATH=. python ingestion/snotel_historical.py

# 10 years of ski-season traffic patterns (~850K rows)
PYTHONPATH=. python ingestion/cdot_historical.py

# Load into DuckDB
PYTHONPATH=. python db/setup.py
```

> **Why isn't the data in the repo?** All data files (~46 MB) are fully regenerable from free public sources. Steps above recreate them in under 5 minutes.

## PostgreSQL for User Accounts

User accounts require PostgreSQL. Without it, the app runs in guest mode (all core features work, but no login/profile/trip tracking).

### Option 1: Docker (recommended)

```bash
docker-compose up -d
```

Add to `.env`:
```
DATABASE_URL=postgresql://powracle_user:your_secure_password@localhost:5432/powracle
```

Run migrations:
```bash
python db/run_migrations.py
```

### Option 2: Native PostgreSQL

**macOS:** `brew install postgresql@15 && brew services start postgresql@15`
**Linux:** `sudo apt install postgresql postgresql-contrib && sudo systemctl start postgresql`
**Windows:** Download from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)

Then create the database:
```bash
psql postgres
CREATE DATABASE powracle;
CREATE USER powracle_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE powracle TO powracle_user;
\q
```

Add `DATABASE_URL` to `.env` and run `python db/run_migrations.py`.

### User Account Features

Once PostgreSQL is set up, the app shows login/register forms. Features include:
- Profile management (home city, ski ability, preferred terrain)
- Season pass tracking with ROI calculation
- Ski day logging
- Trip planning and history
- Season stats dashboard

## FastAPI API

```bash
uvicorn api:app --reload
```

- Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- `GET /health` — health check
- `POST /chat` — send a question, get an answer + ranking

```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Which resort has the most fresh snow?", "messages": [], "selected_passes": ["All"], "start_city": "Denver"}'
```

## Troubleshooting

**"Could not connect to database"**
- Docker: `docker ps | grep powracle-postgres` — if stopped: `docker start powracle-postgres`
- Native: `brew services list` (macOS) or `sudo systemctl status postgresql` (Linux)
- Verify `DATABASE_URL` in `.env` matches your credentials

**"relation does not exist"**
- Run migrations: `python db/run_migrations.py`

**Guest Mode**
- If PostgreSQL isn't available, the app runs in guest mode automatically. All core features work — you just won't have personalization or trip tracking.
