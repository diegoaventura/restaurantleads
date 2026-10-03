# API REST — Restaurant Leads

API v1 bajo el prefijo `/api/v1`. Backend FastAPI; documentación OpenAPI autogenerada
(`/docs` y `/redoc` cuando el backend esté en marcha).

## Convenciones generales

- **Auth**: `Authorization: Bearer <JWT>` (login en `/auth/login`). Expiración corta (60 min).
- **Roles**: `admin` (usuarios, ingesta completa, supresión física RGPD) y `sales` (operación diaria).
- **Paginación**: `?page=1&page_size=25` (`page_size` máx 100). Respuesta:
  ```json
  { "items": [...], "total": 132, "page": 1, "page_size": 25 }
  ```
- **Errores**: formato FastAPI estándar:
  ```json
  { "detail": "Lead no encontrado" }        // 404
  { "detail": "No autorizado" }             // 401
  { "detail": "Requiere rol admin" }        // 403
  ```
- **Timestamps**: ISO 8601 UTC (`2026-10-03T14:30:00Z`).
- **Soft delete**: los restaurantes con `deleted_at != null` quedan excluidos de listados
  (accesibles solo vía export/supresión).

---

## Health

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/api/v1/health` | pública | Liveness + versión |

```json
{ "status": "ok", "version": "0.1.0", "database": "ok" }
```

---

## Auth

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/v1/auth/login` | pública | Devuelve JWT |
| GET | `/api/v1/auth/me` | Bearer | Usuario actual |

```http
POST /api/v1/auth/login
{ "email": "comercial@empresa.com", "password": "••••••" }
→ 200 { "access_token": "eyJ...", "token_type": "bearer" }
```

---

## Users (solo `admin`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/users` | Listado (paginado) |
| POST | `/api/v1/users` | Crear usuario (`email`, `full_name`, `password`, `role`) |
| PATCH | `/api/v1/users/{id}` | Editar (rol, activo, nombre) |

---

## Restaurants / Leads

El lead es 1:1 con el restaurante: se manipula anidado en el recurso.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/restaurants` | Listado con filtros + paginación |
| POST | `/api/v1/restaurants` | Alta manual (crea lead `new`) |
| GET | `/api/v1/restaurants/{id}` | Ficha completa (ver abajo) |
| PATCH | `/api/v1/restaurants/{id}` | Rectificar datos |
| DELETE | `/api/v1/restaurants/{id}` | Soft delete (RGPD: acceso/supresión) |
| GET | `/api/v1/restaurants/{id}/export` | Export JSON completo (portabilidad) |
| PATCH | `/api/v1/restaurants/{id}/lead` | Cambiar `status`/`priority`/`assigned_to` |
| POST | `/api/v1/restaurants/{id}/score/recalculate` | Recalcular score |

**Filtros del listado** (todos opcionales, combinables):

`search` (nombre/teléfono), `city`, `category`, `status`, `platform`, `source`,
`min_score`, `max_score`, `has_phone`, `created_from`, `created_to`,
`sort` (`score`, `updated_at`, `name`) + `order`.

```http
GET /api/v1/restaurants?city=Madrid&status=contacted&min_score=60&sort=score&order=desc&page=1
```

**Ficha completa** (`GET /restaurants/{id}`):

```json
{
  "id": "…", "name": "Kebab Hassan", "phone": "+34612345678", "phone_source": "osm",
  "website": "kebabhassan.es", "city": "Madrid", "category": "kebab",
  "delivery": [
    { "platform": "glovo", "detection_method": "website_link",
      "url": "https://glovoapp.com/…", "last_detected_at": "…" }
  ],
  "lead": {
    "status": "contacted", "score": 87, "priority": "high", "assigned_to": "…",
    "score_reasons": [
      { "factor": "delivery_detectado", "points": 25 },
      { "factor": "zona_cubierta", "points": 20 }
    ]
  },
  "sources": [ { "source": "osm", "external_id": "node/123456" } ],
  "next_follow_up": { "scheduled_at": "2026-10-06T09:00:00Z", "channel": "call" }
}
```

**Cambio de estado** (transiciones validadas según la tabla de `docs/DATABASE.md`):

```http
PATCH /api/v1/restaurants/{id}/lead
{ "status": "follow_up", "priority": "high", "assigned_to": "<user_id>" }
→ 422 { "detail": "Transición inválida: meeting → contacted" }
```

---

## Interactions (historial inmutable)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/restaurants/{id}/interactions` | Historial cronológico (paginado) |
| POST | `/api/v1/restaurants/{id}/interactions` | Registrar contacto |

```http
POST /api/v1/restaurants/{id}/interactions
{
  "channel": "call",
  "occurred_at": "2026-10-03T11:20:00Z",
  "result": "no_answer",
  "notes": "Tono de ocupado a las 11:20"
}
→ 201  { …interacción…,
  "follow_up_created": { "id": "…", "scheduled_at": "2026-10-06T11:20:00Z" } }
```

`result=no_answer` → crea follow-up automático a +3 días (configurable).
No existe DELETE: el historial no se borra.

---

## Follow-ups

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/follow-ups` | `?status=pending&due_on=2026-10-06` / `due_before` |
| GET | `/api/v1/restaurants/{id}/follow-ups` | Los del restaurante |
| POST | `/api/v1/restaurants/{id}/follow-ups` | Programar manualmente |
| PATCH | `/api/v1/follow-ups/{id}` | Acción sobre el seguimiento |

```http
PATCH /api/v1/follow-ups/{id}
{ "action": "postpone", "new_date": "2026-10-08T09:00:00Z", "notes": "Lo pide el dueño" }
```

`action` ∈ `complete` (marca `completed_at`), `postpone` (requiere `new_date`), `cancel`.

---

## Ingesta

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/api/v1/ingestion/connectors` | admin | Conectores disponibles + estado |
| POST | `/api/v1/ingestion/run` | admin | Ejecuta un conector |
| GET | `/api/v1/ingestion/runs/{run_id}` | admin | Resultado de la ejecución |

```http
POST /api/v1/ingestion/run
{
  "connector": "manual_import",
  "params": { "csv_content": "name,phone,city\nKebab Hassan,+34 612 34 56 78,Madrid" },
  "dry_run": true
}
→ 200 {
  "run_id": "…", "dry_run": true,
  "received": 120, "valid": 112, "new": 90,
  "exact_duplicates": 18, "possible_duplicates": 4, "invalid": 8
}
```

Con `dry_run=true` no se escribe nada en BD. El conector `osm` acepta `bbox`/área y
consulta Overpass respetando el intervalo configurado (sin bypass de límites).

---

## Duplicados (cola de revisión)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/duplicates` | Casos marcados como `possible_duplicate_of` (paginado) |
| POST | `/api/v1/duplicates/{restaurant_id}/resolve` | Resolver el caso |

```http
POST /api/v1/duplicates/{restaurant_id}/resolve
{ "action": "keep_both" }        // "merge" (conserva el de más datos) | "keep_both"
```

El **merge nunca es automático**: la deduplicación segura (external_id/phone/web) fusiona
en la ingesta; la dudosa (nombre parecido + cercanía) solo marca y espera revisión humana.

---

## Dashboard y Analytics

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/dashboard/stats` | KPIs del dashboard |

```json
{
  "restaurants_total": 132, "leads_new": 18, "leads_qualified": 12,
  "pending_contact": 30, "follow_ups_due_today": 5, "follow_ups_overdue": 2,
  "interested": 9, "meetings": 4, "customers": 3, "conversion_rate": 0.023
}
```

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/analytics/leads` | Agregado por `group_by=source\|category\|city\|score_range` |
| GET | `/api/v1/analytics/funnel` | Recuento por estado del embudo |

Ambos aceptan `from`/`to`. **Solo métricas descriptivas**: no se infiere causalidad.

```json
{ "dimension": "source", "rows": [
  { "key": "osm", "leads": 100, "contacted": 40, "interested": 20, "customers": 5 },
  { "key": "manual_import", "leads": 32, "contacted": 15, "interested": 12, "customers": 3 } ] }
```

---

## IA

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/ai/generate` | Generar contenido (rate-limited) |
| GET | `/api/v1/restaurants/{id}/ai-generations` | Histórico generado |

```http
POST /api/v1/ai/generate
{ "restaurant_id": "…", "generation_type": "call_script" }
→ 201 {
  "id": "…", "generation_type": "call_script", "prompt_version": "call_script_v1",
  "provider": "groq", "model": "llama-3.3-70b-versatile",
  "generated_content": "«Buenos días, ¿habla con…?»"
}
```

- Solo se envían al LLM los campos definidos en el prompt (nombre, categoría, ciudad,
  plataformas, score...) — nunca datos de más.
- El contenido se **edita y copia manualmente**: no existe endpoint de envío automático.
- Sin `LLM_API_KEY` configurada → `503 { "detail": "IA no configurada" }` y la app funciona sin IA.
