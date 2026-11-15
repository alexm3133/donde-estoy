# Architecture

## Overview

```
 Runner's phone                         Server                       Viewer's phone
┌────────────────────┐   HTTPS POST   ┌──────────────────────┐  WebSocket  ┌──────────────┐
│ LocationProvider   │  positions     │ FastAPI              │  snapshots  │ Viewer page  │
│  → offline buffer  │ ─────────────▶ │  Tracker (state      │ ──────────▶ │  map + ETA   │
│  → uploader        │  (batches)     │   machine) + ETA     │             │  + alerts    │
└────────────────────┘                │  PostgreSQL / SQLite │             └──────────────┘
                                      └──────────────────────┘
```

- The **runner** posts GPS fixes over plain HTTP in batches. HTTP (not a
  socket) because batches are how we catch up after losing coverage, and
  retries are trivial.
- The **server** runs each fix through the tracker, stores the new state and
  pushes a *snapshot* (the full current state) to every viewer of that session.
- The **viewer** loads everything once over HTTP, then listens on a WebSocket.
  Things that depend on the passage of time rather than on new data — the
  countdown, "stopped", "no signal", the safety alert — are derived in the
  browser from the last snapshot and the clock.

## Backend (`backend/app`)

| Module | Role |
| --- | --- |
| `eta/` | **ETA engine.** Pure functions and data: Tobler model, pace calibration, estimate. No I/O. |
| `services/route.py` | Route geometry: resampling, elevation smoothing, snapping a fix to the route. |
| `services/gpx.py` | Safe GPX parsing (`defusedxml`). |
| `services/tracker.py` | Session state machine: filters fixes, detects movement and arrival, feeds the calibration, asks for the ETA. Pure. |
| `services/snapshot.py` | Turns a database row into the public `Snapshot`. |
| `services/hub.py` | In-process pub/sub for WebSocket fan-out. |
| `services/cleanup.py` | Expiry purge and "stop sharing" data wipe. |
| `api/` | HTTP and WebSocket endpoints (thin). |
| `models.py`, `db.py` | SQLAlchemy 2 models; Alembic migrations in `backend/alembic`. |

### Data model

Two tables.

**`sessions`**

| Column | Notes |
| --- | --- |
| `id` | Random id, used by the runner's device |
| `view_token_hash` | SHA-256 of the token in the share link (unique) |
| `runner_token_hash` | SHA-256 of the runner's secret |
| `runner_name`, `activity` | Display name; `run` or `hike` |
| `state` | `active` → `finished` (arrived) or `ended` (stopped sharing) |
| `stall_alert_minutes` | Safety alert threshold chosen by the runner |
| `created_at`, `expires_at`, `ended_at` | Lifetime |
| `dest_lat`, `dest_lon` | Destination |
| `route` (JSON) | Processed route, or NULL for tap-on-map sessions |
| `tracker` (JSON) | `TrackerState`: progress, pace calibration, latest ETA |

**`positions`** — accepted GPS fixes (`session_id`, `lat`, `lon`, `ele`,
`accuracy`, `recorded_at`), kept only to draw the track.

### API

Runner (authenticated with `Authorization: Bearer <runner_token>`):

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/routes/parse` | Parse a GPX upload (stateless preview) |
| `POST` | `/api/sessions` | Start a session → ids, tokens, share URL |
| `GET` | `/api/sessions/{id}` | Own session (resume after reload) |
| `POST` | `/api/sessions/{id}/positions` | Report a batch of fixes |
| `POST` | `/api/sessions/{id}/finish` | "I have arrived" |
| `POST` | `/api/sessions/{id}/stop` | Stop sharing and erase location data |

Viewer (the link token is the only credential):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/view/{token}` | Snapshot + route + track |
| `WS` | `/api/view/{token}/ws` | Live snapshots (`snapshot` / `ping` / `expired`) |

Interactive documentation is served at `/docs`.

### Privacy and security decisions

- Tokens are 128-bit random values; only their hashes are stored, so a
  database leak does not expose live links.
- Unknown, expired and unauthorised sessions all return the same 404.
- Expired sessions stop working immediately (checked on access) and are
  deleted, with their positions, by a background task.
- "Stop sharing" deletes positions, route, destination and tracker state on
  the spot; the empty row remains until expiry only so the link can say
  "sharing has ended".
- After arrival the link lives for a short grace period, then is purged.
- Device clock skew is corrected using the batch's `sent_at`.
- The web server sends `Referrer-Policy: no-referrer` so share links do not
  leak to other sites.

### Scaling note

Live updates use an in-memory hub, so the API must run as **one process**.
That is plenty for a personal deployment. To scale out, implement the same
two-method interface (`subscribe`, `publish`) on Redis pub/sub or PostgreSQL
`LISTEN/NOTIFY`.

## Frontend (`frontend/src`)

| Folder | Role |
| --- | --- |
| `theme/` | **Design tokens** (`tokens.css`), base styles, theme switch |
| `i18n/` | Translations (es, ca, en) |
| `api/` | Typed API client and types |
| `domain/` | Pure logic with tests: live status, alerts, formatting |
| `location/` | `LocationProvider` interface + browser and simulated providers |
| `tracking/` | Runner side: offline buffer/uploader, wake lock, session storage |
| `live/` | Viewer side: live session hook, notifications |
| `components/` | Map, ETA hero, elevation profile, alert banner… |
| `pages/` | `HomePage` (set-up), `RunPage` (sharing), `ViewerPage` (the link) |

### Replacing the location source

`createLocationProvider()` in `location/index.ts` is the only place that
chooses where positions come from. A native build adds a provider backed by a
Capacitor background-geolocation plugin and returns it there when
`Capacitor.isNativePlatform()` is true.

### Status and alerts

`domain/status.ts` derives `moving / stopped / no_signal / …` from a snapshot
and the current (server-corrected) time. `domain/alerts.ts` decides which
alert is on screen and which ones to announce, given what was already
announced. Both are pure and unit-tested; the viewer page only renders the
result and triggers the sound / notification.
