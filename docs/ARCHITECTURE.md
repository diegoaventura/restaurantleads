# Arquitectura — Restaurant Leads

Aplicación web interna (SaaS single-tenant) de **captación de restaurantes y CRM** para una
empresa de reparto de pedidos. Convierte el proceso manual de prospección (buscar → detectar
delivery → localizar contacto → llamar → registrar → hacer seguimiento → convertir) en un
sistema de captación de leads con ingesta de datos, deduplicación, scoring, CRM, IA de apoyo
y analítica.

> Convención del proyecto: **documentación en español, código en inglés** (identificadores,
> comentarios clave y mensajes de log en inglés).

---

## 1. Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Base de datos | PostgreSQL 16 (Docker) |
| Frontend | React 18+, TypeScript, Vite, Tailwind CSS |
| Testing | Pytest + httpx (API) / Vititest (frontend) |
| Infraestructura | Docker + Docker Compose |
| IA | Capa `LLMProvider` (API OpenAI-compatible); proveedor gratuito: Groq o Gemini |

---

## 2. Diagrama de componentes

```
┌─────────────────────────── FUENTES DE DATOS ────────────────────────────┐
│  CSV manual (manual_import) │ OpenStreetMap (Overpass) │ Google Places* │
│                             │  pública, gratuita       │ opcional, pago  │
└──────────────┬──────────────┴───────────┬───────────────┴────────────────┘
               │        RestaurantCandidate (modelo normalizado)
               ▼
        ┌───────────────────────────────────────────┐
        │ INGESTA / PIPELINE                        │
        │ extract → normalize → validate →           │
        │ deduplicate → load                        │
        └───────────────┬───────────────────────────┘
                        ▼
        ┌───────────────────────────────────────────┐
        │ LIMPIEZA Y NORMALIZACIÓN                  │
        │ nombres, teléfonos (E.164, phonenumbers), │
        │ direcciones, dominios web                 │
        └───────────────┬───────────────────────────┘
                        ▼
        ┌───────────────────────────────────────────┐
        │ DEDUPLICACIÓN (reglas + rapidfuzz)        │
        │ match seguro → merge                      │
        │ match dudoso → cola de revisión           │
        └───────────────┬───────────────────────────┘
                        ▼
                ┌──────────────┐
                │ PostgreSQL   │──── ENRIQUECIMIENTO (web del restaurante:
                └──────┬───────┘      enlaces a plataformas, email, teléfono)
                       │               cada dato guarda su fuente + fecha
                       ▼
                ┌──────────────┐
                │ LEAD SCORING │ 0–100, reglas configurables (no hardcodeadas),
                └──────┬───────┘ con explicación de factores
                       ▼
        ┌───────────────────────────────────────────┐
        │ CRM (estados, interacciones, notas,       │
        │ follow-ups, historial inmutable)          │
        └──────┬──────────────────────┬────────────┘
               ▼                      ▼
        ┌──────────────┐       ┌──────────────┐
        │ IA (opcional)│       │ ANALÍTICA    │
        │ briefing,   │       │ métricas     │
        │ guiones,     │       │ descriptivas │
        │ mensajes     │       └──────────────┘
        │ (revisables) │
        └──────────────┘
                       ▼
        ┌───────────────────────────────────────────┐
        │ CONTACTO (tel: / wa.me / copiar) +        │
        │ registro de la acción como interacción    │
        └───────────────────────────────────────────┘
```

\* El conector `google_places` queda **definido pero no implementado**: solo se activará si
en el futuro se dispone de clave y presupuesto. No se implementa scraping de plataformas de
delivery (Glovo, Uber Eats, Just Eat...): sus términos de servicio lo prohíben y no ofrecen
API pública para este caso.

---

## 3. Estructura de carpetas

```
restaurant-leads/
├── backend/
│   ├── app/
│   │   ├── api/            # Routers HTTP (api/v1/...)
│   │   ├── core/           # config (env), security (JWT), logging
│   │   ├── models/         # Modelos SQLAlchemy (ORM)
│   │   ├── schemas/        # Esquemas Pydantic (request/response)
│   │   ├── services/       # Lógica de dominio: scoring, dedup, enrichment, analytics
│   │   ├── ingestion/      # Pipeline + conectores (base.py + connectors/)
│   │   ├── ai/             # LLMProvider + prompts versionados
│   │   └── db/             # Sesión, Base declarativa, Alembic
│   ├── tests/              # Pytest: modelos, API, scoring, dedup, follow-ups...
│   └── pyproject.toml
├── frontend/              # React + TS + Vite + Tailwind (dashboard, tabla leads, ficha)
├── docs/                   # ARCHITECTURE, ROADMAP, DATABASE, API (este documento)
├── docker-compose.yml      # Milestone 0: postgres. Milestone 12: backend + frontend
├── .env.example
└── README.md
```

---

## 4. Decisiones técnicas (y por qué)

| # | Decisión | Justificación | Alternativas descartadas |
|---|---|---|---|
| D1 | **Single-tenant** | Una sola empresa usa la herramienta. Sin `company_id` ni aislamiento por tenant → MVP más simple. El diseño (auth propia, UUID, fuentes por registro) permite añadir multi-tenancy después sin reescribir. | Multi-tenant desde el día 1 (overengineering) |
| D2 | **Monorepo** (backend + frontend + docs) | Un solo `docker compose up`, una sola historia en git, docs junto al código. | Dos repositorios (fricción innecesaria) |
| D3 | **PostgreSQL 16 con enums nativos y UUID** | Los estados (`lead_status`, `channel`, `platform`...) son dominio cerrado: el enum nativo impide valores inválidos en BD, no solo en la app. UUID permite exportar/mergear sin colisiones. | TEXT + CHECK (más laxo), IDs enteros (frágil al exportar) |
| D4 | **SQLAlchemy 2 async + Alembic** | Pool de conexiones asíncrono natural en FastAPI; Alembic da migraciones versionadas y reproducibles. | SQL crudo (sin versionado), sync ORM (bloquea el event loop) |
| D5 | **Auth: JWT corto + roles (`admin`, `sales`)** | Herramienta interna con pocos usuarios: sin refresh tokens ni OAuth. El JWT corto (60 min) simplifica el estado. `bcrypt` para contraseñas. | Sesiones server-side (requiere Redis/store), OAuth (innecesario) |
| D6 | **Conectores de ingesta con interfaz común** | Cada fuente implementa `Connector` y devuelve `RestaurantCandidate`. Añadir una fuente = un archivo nuevo, sin tocar el resto. Ver `docs/ROADMAP.md` M3. | Ingesta acoplada a una única fuente |
| D7 | **OSM/Overpass como fuente automática** | Gratuita, legal y con datos reales de restaurantes en España (nombre, teléfono, web, cuisine, coordenadas). Ideal para demo real. | Scraping de directorios (ToS), Google Places (pago) |
| D8 | **Detección de delivery: web propia + confirmación manual** | Fetch puntual y respetuoso de la web pública del restaurante buscando enlaces a plataformas (legal), + marcado manual del comercial en la llamada. | Scraping de Glovo/Uber Eats/Just Eat (**prohibido por sus ToS**) |
| D9 | **`LLMProvider` OpenAI-compatible** | Un cliente abstracto con el formato de mensajes más extendido. Groq y Gemini (free tier) encajan; cambiar de proveedor = cambiar config, no código. La IA **solo genera textos revisables**, nunca datos. | SDK acoplado a un proveedor; IA que rellena datos (riesgo de alucinación) |
| D10 | **Scoring configurable** | Las reglas (pesos) viven en configuración (JSON en BD, editable), no en el código. Cada score guarda sus razones (`score_reasons` JSONB) → explicable. | Criterios hardcodeados |
| D11 | **Librerías estándar para lo delicado** | `phonenumbers` (E.164, region ES) y `rapidfuzz` (matching difuso) para normalización/deduplicación. | Implementaciones propias (error-prone) |
| D12 | **Soft delete + borrado en cascada** | RGPD: supresión de un restaurante y todos sus datos asociados; exportación JSON por restaurante. El historial de interacciones **nunca se borra** salvo supresión RGPD. | DELETE físico en la UI (pérdida de historial) |
| D13 | **Los mensajes de IA nunca se envían solos** | Todo contenido generado pasa por revisión humana antes de cualquier acción comercial. Guardamos `prompt_version`, `provider`, `model` y contenido. | Envío automatizado (riesgo legal + reputacional) |

---

## 5. Flujo de datos (paso a paso)

1. **Extract** — un conector (CSV manual u Overpass) produce `RestaurantCandidate`s.
2. **Normalize** — nombres (minúsculas, sin acentos/símbolos), teléfonos (E.164 con `phonenumbers`, región ES), webs (dominio raíz), direcciones/ciudad.
3. **Validate** — Pydantic valida tipos; se descartan candidatos sin nombre ni teléfono ni web (imposibles de contactar).
4. **Deduplicate** — contra lo ya existente en BD, por prioridad: `external_id+source` → teléfono → dominio web → nombre+dirección → similitud+proximidad. Dudoso → cola de revisión (nunca merge automático).
5. **Load** — INSERT del restaurante + `restaurant_source` + creación del lead (`status=new`).
6. **Enrichment** — asíncrono/programado: detectar enlaces de delivery en la web del restaurante, verificar teléfono/email. Cada campo guarda `*_source` y `*_verified_at`; **nunca se sobrescribe en silencio**.
7. **Scoring** — calcula 0–100 con las reglas configuradas y guarda las razones.
8. **CRM** — el comercial trabaja la ficha: llama (`tel:`/`wa.me`), registra interacción con resultado, programa follow-up.
9. **Analytics** — métricas descriptivas agregadas (sin asumir causalidad).

---

## 6. Seguridad

- **Secretos**: solo por variables de entorno (`.env` fuera de git; `.env.example` como plantilla).
- **AuthN**: JWT HS256, expiración corta; contraseñas con bcrypt.
- **AuthZ**: rol `admin` (usuarios, ingesta completa) vs `sales` (operación diaria). Endpoints protegidos por dependencia FastAPI.
- **Inputs**: Pydantic valida todo; enums en BD.
- **Rate limiting**: en endpoints de ingesta y IA (son los más costosos).
- **CORS**: solo el origen del frontend (`FRONTEND_URL`).
- **Logs**: nunca se registran secretos ni contenido de mensajes personales.

---

## 7. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Docker Desktop no instalado (entorno actual) | Bloquea BD y desarrollo local | Instalarlo antes del Milestone 1; mientras tanto, M0 solo produce docs/config |
| No existe API pública de plataformas de delivery | Detección de delivery incompleta | Web del restaurante + confirmación manual; `detection_method` documenta el origen de cada detección |
| Calidad desigual de datos OSM (teléfonos viejos) | Leads con datos incorrectos | Estados `wrong_number`/`out_of_area`, verificación con timestamps, enriquecimiento posterior |
| Coste/limitaciones de la capa IA | Funciones IA degradadas | Free tiers (Groq/Gemini); la app es 100% funcional sin IA |
| Alucinaciones de IA | Textos con datos falsos | La IA solo recibe datos del restaurante y genera *texto*; revisión humana obligatoria antes de usar |
| RGPD | Requisito legal | Minimización de datos, fuente y finalidad registradas, export/supresión por restaurante (ver `docs/DATABASE.md` §RGPD) |
| Alcance del MVP (13 milestones) | Retraso / código sin validar | Demo con datos ficticios tras M6 antes de continuar; cada milestone deja el proyecto funcionando |

---

## 8. Evolución futura (explícitamente fuera del MVP)

- Multi-tenancy (SaaS a varias empresas) — añadir `company_id` + aislamiento.
- Orquestación con n8n/Airflow — solo si las tareas programadas se quedan cortas.
- WhatsApp Business API / email transaccional — con mecanismos de consentimiento y control.
- Redis para cache/rate-limit distribuido — cuando haya más de una instancia.
- Tri-gramas + PostGIS para matching geográfico avanzado — cuando el volumen lo justifique.
