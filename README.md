# Restaurant Leads

Aplicación web interna de **captación de restaurantes y CRM** para una empresa de reparto
de pedidos: sustituye el prospección manual (buscar restaurantes con delivery → localizar
contacto → llamar → registrar → hacer seguimiento → convertir) por un sistema con ingesta
de datos, deduplicación, lead scoring explicable, CRM con seguimientos y analítica.

> Estado actual: **Milestone 5 completado** (arquitectura, modelos, migraciones, backend
> FastAPI con auth, ingesta con deduplicación, scoring explicable y CRM con seguimientos).
> El desarrollo avanza por milestones — ver [docs/ROADMAP.md](docs/ROADMAP.md).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Base de datos | PostgreSQL 16 (Docker) |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Testing | Pytest (backend) / Vitest (frontend) |
| Infraestructura | Docker + Docker Compose |
| IA (opcional) | Capa `LLMProvider` OpenAI-compatible (free tier) |

## Documentación

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — componentes, flujo de datos, decisiones, riesgos
- [docs/ROADMAP.md](docs/ROADMAP.md) — 13 milestones con criterios de verificación
- [docs/DATABASE.md](docs/DATABASE.md) — esquema PostgreSQL, enums, índices, RGPD
- [docs/API.md](docs/API.md) — API REST v1 con ejemplos

## Estructura

```
restaurant-leads/
├── backend/    # FastAPI: api, core, models, schemas, services, ingestion, ai, db
├── frontend/   # React + TS + Vite + Tailwind (Milestone 6)
├── docs/       # arquitectura, roadmap, base de datos, API
└── docker-compose.yml   # PostgreSQL (backend/frontend se añaden en M12)
```

## Puesta en marcha (M1 — backend: modelos + migraciones + seed)

Requisitos: Docker Desktop (en ejecución), Python 3.11+.

```bash
# 1. Configurar entorno (los valores por defecto ya coinciden con docker-compose)
cp .env.example .env        # ajusta SECRET_KEY y POSTGRES_PASSWORD

# 2. Levantar PostgreSQL
docker compose up -d postgres

# 3. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"

# 4. Migraciones
alembic upgrade head

# 5. Datos ficticios de desarrollo (2 usuarios + 3 restaurantes)
python scripts/seed.py         # usuarios: admin@example.com / ventas@example.com (pass: demo1234)

# 6. Tests (usan una BD desechable restaurant_leads_test)
pytest

# 7. API (http://127.0.0.1:8000/docs — Swagger autogenerado)
python run.py
#    login: admin@example.com / demo1234 (rol admin)
#    login: ventas@example.com / demo1234 (rol sales)
```

> Nota Windows: `run.py` lanza uvicorn con `loop="none"` — uvicorn ≥0.36 fuerza
> ProactorEventLoop en Windows, incompatible con psycopg async. En Linux/macOS
> (`uvicorn app.main:app`) no hace falta.

El frontend (vite) llega en el Milestone 6; el compose completo (backend +
frontend + postgres) en el Milestone 12.

## Variables de entorno

Ver [.env.example](.env.example). Resumen:

- `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` — seguridad JWT
- `POSTGRES_*`, `DATABASE_URL` — base de datos
- `OVERPASS_*` — ingesta OpenStreetMap (API pública, sin clave)
- `LLM_PROVIDER`, `LLM_API_KEY` — capa IA (opcional, Milestone 8)

Nunca se suben secretos al repositorio (`.env` está en `.gitignore`).

## Desarrollo

El proyecto avanza **milestone a milestone**. Reglas: explicación antes de cada uno,
tests tras cada uno, sin APIs/credenciales inventadas, sin scraping contrario a ToS,
sin envíos automatizados sin revisión humana. Detalle completo en `docs/ROADMAP.md`.

## Privacidad

Aplicación diseñada conforme a RGPD: datos de contacto **profesionales** de negocios,
fuente y finalidad registradas por registro, exportación y supresión por restaurante.
Ver `docs/DATABASE.md` § RGPD.
