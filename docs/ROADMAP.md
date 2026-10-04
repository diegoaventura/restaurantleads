# Roadmap — Restaurant Leads

13 milestones (0–12). Cada uno:

- tiene un **objetivo claro** y **criterios de verificación**,
- deja el proyecto **funcionando** al terminar,
- incluye tests de lo que añade,
- se explica (objetivo, archivos, dependencias, riesgos) **antes** de empezarlo
  y se resume (tests, errores, cambios) **al terminarlo**.

Convenciones de desarrollo (aplican a todos los milestones):

1. Sin cambios masivos sin aviso previo.
2. No inventar APIs ni credenciales. Nada de datos reales en tests.
3. Sin scraping que incumpla ToS, sin saltar CAPTCHAs/bloqueos, sin automatización
   de WhatsApp/email sin control humano.
4. Separación estricta: frontend / backend / database / ingestion / ai / scoring.
5. Simplicidad antes que features. El diseño debe permitir evolucionar, no pre-implementarlo todo.

---

## M0 — Análisis + arquitectura ✅ *(este milestone)*

**Objetivo**: base del repositorio y decisiones documentadas.

**Entregables**: estructura de carpetas, git, `docker-compose.yml` (postgres), `.env.example`,
`.gitignore`, README y `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DATABASE.md`, `docs/API.md`.

**Verificación**: estructura y docs existen y son coherentes entre sí. *(El arranque de
Postgres requiere Docker Desktop, pendiente de instalar — se verifica en M1.)*

---

## M1 — PostgreSQL + modelos + migraciones ✅

**Objetivo**: esquema completo de las 9 entidades en SQLAlchemy + migración Alembic.

**Entregables**: `backend/pyproject.toml` (deps), modelos, `alembic` configurado, migración
inicial completa (tablas, enums, constraints, índices), seed mínimo (3 restaurantes ficticios).

**Nota de implementación**: los enums nativos se crean/borran explícitamente en la migración
(`postgresql.ENUM` con `create_type=False` en las tablas) para que `downgrade base && upgrade
head` sea totalmente reversible — el `drop_table` autogenerado dejaría tipos huérfanos.

**Verificación** ✅: `docker compose up -d postgres` sano → `alembic upgrade head` →
`alembic downgrade base && alembic upgrade head` reversible → `alembic check` sin
diferencias → tests de modelos en verde → seed cargado.

---

## M2 — Backend FastAPI (esqueleto + auth + CRUD) ✅

**Objetivo**: app FastAPI ejecutable con auth JWT, CRUD de restaurants/leads y paginación.

**Entregables**: config (env), logging, seguridad (bcrypt + JWT + roles), routers
`auth`, `restaurants` (+ sub-recursos básicos), `users` (admin), `health`, manejo de errores.

**Nota de implementación**: en Windows, uvicorn ≥0.36 fuerza ProactorEventLoop (incompatible
con psycopg async). Solución: `run.py` fija la política del selector y lanza con `loop="none"`.

**Verificación** ✅: `python run.py` arranca; login devuelve token; endpoints protegidos
responden 401/403 según rol; transiciones de estado del lead validadas (422 para sales,
override para admin); 32 tests en verde (10 de modelos + 22 de API).

---

## M3 — Ingesta + normalización + deduplicación ✅

**Objetivo**: pipeline `extract → normalize → validate → deduplicate → load` con dos conectores.

**Entregables**: `ingestion/base.py` (interfaz `Connector` + `RestaurantCandidate`),
`connectors/manual_import.py` (CSV), `connectors/osm.py` (Overpass, rate-limited),
servicios de normalización (`phonenumbers`, E.164) y matching (`rapidfuzz`), cola de duplicados
(`GET /duplicates`, resolver merge/keep_both), endpoint `POST /ingestion/run` (dry_run).

**Notas de implementación**:
- Matching priority 1-4 (external_id/phone/website/name+address) → fusión automática **solo
  rellenando huecos** (nunca sobrescribe datos existentes); priority 5 (similitud ≥85 +
  proximidad ≤300 m, misma ciudad y con coordenadas) → cola de revisión humana, nunca merge
  automático. Nombres repetidos sin coordenadas NO se marcan (pueden ser franquicias).
- `dry_run` ejecuta el pipeline completo y hace rollback: los contadores son reales.
- El historial de ejecuciones (`GET /ingestion/runs/{id}`) queda **aplazado** (requiere tabla
  propia); candidato para un milestone posterior si aporta valor operativo.
- El conector OSM se testea sin red (parseo puro de elementos Overpass); las llamadas reales
  respetan intervalo configurado y timeout.

**Verificación** ✅: CSV ficticio carga sin duplicar (2ª ejecución idempotente: 0 nuevos);
dry_run no escribe; duplicado dudoso a la cola + resolución merge/keep_both funcionales;
demo real ejecutada contra la BD de desarrollo; 73 tests en verde (15 normalización +
10 deduplicación + 9 ingesta API + 8 OSM + previos).

---

## M4 — Scoring ✅

**Objetivo**: score 0–100 configurable y explicable por restaurante.

**Entregables**: `services/scoring.py` con reglas leídas de configuración (no hardcodeadas),
`score_reasons` (factores positivos/negativos), recálculo manual (`POST /restaurants/{id}/score/recalculate`),
scoring automático tras alta manual e ingesta, seed con scores reales.

**Notas de implementación**:
- `backend/scoring_rules.json` (ruta configurable con `SCORING_RULES_PATH`): pesos, reglas
  activables (`enabled`), ciudades de servicio y categorías objetivo. Cambiar un peso = editar
  el JSON + recalcular: **cero cambios de código**.
- Los predicados son código tipado (sin eval de expresiones, seguro y testeable); un id
  desconocido en el JSON falla de forma explícita (`ScoringConfigError`).
- Reglas M4: delivery (+25), zona (+20), teléfono (+10), web (+5), email (+5), categoría
  objetivo (+10); negativas: posible duplicado pendiente de revisión (-15), sin datos de
  contacto (-20). El score se limita a 0..100 (coincide con el CHECK de la BD).
- `score_reasons` guarda `{factor, label, points}` — nunca un número sin explicación.
- Reglas futuras (reseñas/actividad, varias ubicaciones) llegan con el enriquecimiento (M5+).

**Verificación** ✅: score alto/medio/bajo con razones correctas; regla desactivada no puntúa;
cambiar pesos cambia el score (sin tocar código); negativos y clamps 0/100; endpoint de
recálculo baja el score al quitar el teléfono; ingesta y alta manual puntúan automáticamente;
92 tests en verde (19 nuevos de scoring).

---

## M5 — CRM

**Objetivo**: ciclo comercial completo: estados, interacciones, notas, historial, follow-ups.

**Entregables**: transiciones de `lead_status` validadas, `POST /restaurants/{id}/interactions`
(puede crear follow-up automáticamente según resultado), follow-ups CRUD
(completar/posponer/cancelar), historial inmutable (nunca DELETE de interacciones).

**Verificación**: tests de transiciones válidas/inválidas; registrar `no_answer` el 03/10
crea follow-up el 06/10; `test_follow_up_status` en verde.

---

## M6 — Frontend + dashboard

**Objetivo**: SPA React+TS+Vite+Tailwind con login, dashboard y **tabla de leads** (pantalla principal).

**Entregables**: auth (login/ruedas), dashboard con KPIs, tabla de leads con todos los
filtros (ciudad, categoría, score, estado, plataforma, fuente, fecha), paginación,
diferenciación visual de estados, flujo de 5 clics: abrir → ver → contactar → registrar → programar.

**Verificación**: build sin errores TS; flujo completo con seed ficticio; filtro+ordenación
combinados funcionan. **Demo con el equipo tras este milestone antes de seguir.**

---

## M7 — Ficha del restaurante

**Objetivo**: página individual completa.

**Entregables**: datos + fuentes por campo, delivery detectado (plataforma/fecha/método),
score con explicación, CRM (estado/responsable/notas), historial cronológico, próximo
seguimiento, acciones rápidas (llamar, WhatsApp, copiar teléfono/email/mensaje) que
registran interacción.

**Verificación**: ficha refleja un restaurante del seed con todas sus secciones; las
acciones rápidas quedan registradas como interacciones.

---

## M8 — IA

**Objetivo**: capa `LLMProvider` con 4 generaciones revisables (briefing, guion de llamada,
mensaje comercial, seguimiento).

**Entregables**: abstracción + implementación OpenAI-compatible (Groq/Gemini free tier,
config por env), prompts versionados, `ai_generations` guarda prompt_version/provider/model,
UI de generar → **revisar/editar** → copiar. Nada se envía automáticamente.

**Verificación**: generación con datos del seed produce texto coherente; sin API key la app
sigue funcionando (IA desactivada); tests de la capa con un provider mock.

---

## M9 — Follow-ups avanzados + notificaciones internas

**Objetivo**: gestión diaria de seguimientos pendientes.

**Entregables**: vista "pendientes hoy/esta semana", completar/posponer/cancelar con nota,
"5 seguimientos pendientes hoy" en dashboard, notificación in-app (badge) — sin email externo aún.

**Verificación**: `test_follow_up_status` ampliado (pendiente→completado/pospuesto/cancelado,
vencidos aparecen en el listado del día).

---

## M10 — Analytics

**Objetivo**: métricas descriptivas del embudo.

**Entregables**: leads por estado, tasa de respuesta/interés, reuniones, clientes, conversión
agregada por fuente/categoría/ciudad/rango de score. Sin inferencia causal.

**Verificación**: con el seed, las cifras del embudo cuadran con los datos; tests de agregaciones.

---

## M11 — Testing completo

**Objetivo**: consolidar cobertura de todo lo anterior.

**Entregables**: suites `test_duplicate_detection`, `test_phone_normalization`,
`test_lead_scoring`, `test_follow_up_status`, auth/permisos, API, modelos. CI-local
(instrucción en README) para ejecutar todo en un comando.

**Verificación**: `pytest` completo en verde con datos ficticios únicamente.

---

## M12 — Docker completo + deployment

**Objetivo**: `docker compose up` levanta todo.

**Entregables**: servicios `backend` (uvicorn) y `frontend` (build estático + nginx) en el
compose, README final (instalación, env, migraciones, seed, tests, despliegue), seed de ~50
restaurantes ficticios variados.

**Verificación**: `docker compose up --build` → login → dashboard poblado con seed; tests
corren dentro del contenedor backend.
