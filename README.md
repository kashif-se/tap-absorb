# tap-absorb

<img src="docs/absorb-logo.png" alt="Absorb LMS" height="40">

[![PyPI version](https://img.shields.io/pypi/v/tap-absorb?color=blue&label=PyPI)](https://pypi.org/project/tap-absorb/)
[![Python versions](https://img.shields.io/pypi/pyversions/tap-absorb)](https://pypi.org/project/tap-absorb/)
[![Built with the Meltano SDK](https://img.shields.io/badge/Built%20with%20the%20Meltano%20SDK-✔-blueviolet)](https://sdk.meltano.com)
[![License](https://img.shields.io/github/license/kashif-se/tap-absorb)](LICENSE)

`tap-absorb` is a [Singer](https://www.singer.io/) tap for [Absorb LMS](https://www.absorblms.com/), built with the [Meltano Singer SDK](https://sdk.meltano.com).

It extracts data from the [Absorb Integration API v2](https://docs.myabsorb.com/integration-api/v2/docs) and emits Singer-compatible `RECORD`, `SCHEMA`, and `STATE` messages that can be loaded into any Singer-compatible destination (Snowflake, BigQuery, Postgres, Redshift, etc.).

## Getting Started

### Prerequisites

- Python 3.8 or higher
- An Absorb LMS account with admin access
- A Private API Key (obtained from **Absorb Portal → Settings → Integrations → API Key**)

### Installation

**With pip:**
```bash
pip install tap-absorb
```

**From source:**
```bash
git clone https://github.com/kashif-se/tap-absorb.git
cd tap-absorb
pip install -e ".[dev]"
```

### Configuration

Create a `tap-config.json` file:

```json
{
  "base_url": "https://rest.myabsorb.com",
  "private_key": "YOUR_PRIVATE_API_KEY",
  "username": "api.user@yourcompany.com",
  "password": "YOUR_ADMIN_PASSWORD",
  "start_date": "2022-01-01T00:00:00Z",
  "page_size": 500
}
```

> ⚠️ Never commit credentials to source control. Use environment variables or a secrets manager instead.

**Configure via environment variables:**
```bash
export TAP_ABSORB_PRIVATE_KEY=YOUR_PRIVATE_API_KEY
export TAP_ABSORB_USERNAME=api.user@yourcompany.com
export TAP_ABSORB_PASSWORD=YOUR_ADMIN_PASSWORD
```

---

## Settings

| Setting | Required | Default | Kind | Description |
|---|---|---|---|---|
| `base_url` | No | `https://rest.myabsorb.com` | `string` | Absorb API root URL. See [Region URLs](#region-urls) below. |
| `private_key` | **Yes** | — | `password` | `X-API-Key` from Absorb portal. Required on every request. |
| `username` | **Yes** | — | `string` | Admin username for the `/authenticate` endpoint. |
| `password` | **Yes** | — | `password` | Admin password for the `/authenticate` endpoint. |
| `start_date` | No | — | `date_iso8601` | UTC datetime for incremental sync lower bound. E.g. `2022-01-01T00:00:00Z`. |
| `page_size` | No | `500` | `integer` | Records per API call (1–1000). |
| `user_agent` | No | `tap-absorb/0.1.0 Singer` | `string` | `User-Agent` header sent with every request. |
| `flattening_enabled` | No | — | `boolean` | Flatten nested JSON objects into top-level columns. |
| `flattening_max_depth` | No | — | `integer` | Max nesting depth to flatten when flattening is enabled. |
| `stream_maps` | No | — | `object` | Inline stream-map config for renaming/filtering streams. |
| `stream_map_config` | No | — | `object` | Variables available to `stream_maps` expressions. |

### Region URLs

| Region | Production | Sandbox |
|---|---|---|
| US | `https://rest.myabsorb.com` | `https://rest.sandbox.myabsorb.com` |
| EU | `https://rest.myabsorb.eu` | `https://rest.sandbox.myabsorb.eu` |
| AU | `https://rest.myabsorb.com.au` | `https://rest.sandbox.myabsorb.com.au` |
| CA | `https://rest.myabsorb.ca` | `https://rest.sandbox.myabsorb.ca` |

---

## Capabilities

| Capability | Supported |
|---|---|
| `state` | ✅ Incremental syncs with persistent state |
| `catalog` | ✅ Stream/property selection |
| `discover` | ✅ Schema discovery |
| `about` | ✅ Metadata via `--about` flag |
| `stream-maps` | ✅ Inline transforms via Singer SDK |
| `schema-flattening` | ✅ Nested JSON flattening |

---

## Supported Streams

All streams use **incremental replication** on the `dateEdited` field.

| Stream | Endpoint | Primary Key | Notes |
|---|---|---|---|
| `departments` | `GET /departments` | `id` | Org structure / hierarchy |
| `categories` | `GET /categories` | `id` | Course taxonomy |
| `groups` | `GET /groups` | `id` | Static & dynamic user groups |
| `courses` | `GET /courses` | `id` | All course types |
| `course_bundles` | `GET /courseBundles` | `id` | Bundled course sets |
| `curricula` | `GET /curricula` | `id` | Required course sequences |
| `instructor_led_courses` | `GET /instructorLedCourses` | `id` | ILT / VILT courses |
| `learning_paths` | `GET /learningPaths` | `id` | Ordered course sequences |
| `users` | `GET /users` | `id` | All learner and admin accounts |
| `enrollments` | `GET /users/{id}/enrollments` | `id` | Child of `users`; state partitioned per user |
| `certificates` | `GET /certificates` | `id` | Completion certificates |
| `external_training` | `GET /externalTrainings` | `id` | Externally completed training |
| `attendances` | `GET /attendances` | `id` | ILT session attendance records |

### Child Streams

`enrollments` is a **child stream** of `users`. The Singer SDK calls the enrollments endpoint once per user and injects the `userId` into each enrollment record. State is partitioned by `user_id`, so each user's sync watermark is tracked independently.

---

## Authentication

The tap authenticates via the Absorb `/authenticate` endpoint (username + password + private key). The returned bearer token is:

- Valid for **4 hours**
- **Automatically refreshed** ~60 seconds before expiry
- **Cached** for the duration of a tap run (all streams share the same token)

> **Tip:** Create a dedicated API-only admin user in Absorb rather than using a personal admin account. This ensures token invalidation does not affect interactive users and gives you a clear audit trail.

---

## Incremental Replication

All streams use `dateEdited` as the replication key. On each run, the tap:

1. Reads the saved state (`STATE` message) for the stream.
2. Passes `_filter=dateEdited ge datetime'<last_sync>'` to the API.
3. Sorts results by `dateEdited` ascending for consistent pagination.
4. Emits records and writes an updated state on completion.

On the **first run** (no saved state), `start_date` is used as the lower bound. If `start_date` is not set, all records are returned.

---

## Usage

### Singer (standalone)

**Discovery:**
```bash
tap-absorb --config tap-config.json --discover > catalog.json
```

**Full sync:**
```bash
tap-absorb --config tap-config.json --catalog catalog.json \
  | target-snowflake --config target-config.json
```

**Incremental sync with state:**
```bash
# First run — no state
tap-absorb --config tap-config.json --catalog catalog.json \
  | target-snowflake --config target-config.json \
  | tail -1 > state.json

# Subsequent runs — use saved state
tap-absorb --config tap-config.json --catalog catalog.json --state state.json \
  | target-snowflake --config target-config.json \
  | tail -1 > state.json
```

**Select specific streams only:**
```bash
# Edit the catalog to mark only desired streams as "selected": true
tap-absorb --config tap-config.json --discover \
  | jq '.streams[] |= . + {"metadata": [{"breadcrumb": [], "metadata": {"selected": true}}]}' \
  > catalog.json
```

### Meltano

**Add the extractor:**
```bash
meltano add extractor tap-absorb
```

**Configure — sensitive values go to `.env`, non-sensitive to `meltano.yml`:**
```bash
# Sensitive credentials → stored in .env (never in meltano.yml)
meltano config --store=dotenv tap-absorb set private_key YOUR_KEY
meltano config --store=dotenv tap-absorb set password YOUR_PASSWORD

# Non-sensitive settings → stored in meltano.yml as normal
meltano config tap-absorb set username api.user@company.com
meltano config tap-absorb set start_date 2022-01-01T00:00:00Z
```

Alternatively, copy `.env.example` to `.env` and fill in the values directly — the tap reads `TAP_ABSORB_PRIVATE_KEY`, `TAP_ABSORB_PASSWORD`, and `TAP_ABSORB_USERNAME` automatically:
```bash
cp .env.example .env
# edit .env with your credentials
```

**Test configuration:**
```bash
meltano config tap-absorb test
```

**Run a pipeline:**
```bash
meltano run tap-absorb target-snowflake
```

**Select specific streams:**
```bash
meltano select tap-absorb users '*'
meltano select tap-absorb enrollments '*'
meltano select tap-absorb courses '*'
```

**View discovered streams:**
```bash
meltano invoke tap-absorb --about --format=json
```

---

## Rate Limiting

The Absorb API allows **200 requests/second** with an additional burst buffer of 100. The tap handles `429 Too Many Requests` responses automatically with exponential backoff (up to 5 retries, max 60-second wait with jitter).

---

## Schema Notes

Schemas are defined in `tap_absorb/schemas/` as JSON Schema files. All schemas use `additionalProperties: true` to ensure any undocumented API fields pass through to the target without being dropped.

Key fields present on all streams:

| Field | Type | Description |
|---|---|---|
| `id` | `string` (UUID) | Primary key |
| `dateAdded` | `string` (datetime) | Record creation timestamp |
| `dateEdited` | `string` (datetime) | Last modification timestamp (replication key) |

---

## Development

### Setup

```bash
git clone https://github.com/kashif-se/tap-absorb.git
cd tap-absorb
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check tap_absorb/
```

### Adding a New Stream

1. Add a JSON schema to `tap_absorb/schemas/<stream_name>.json`
2. Create a stream class in `tap_absorb/streams.py` extending `AbsorbStream`
3. Register the stream in `TapAbsorb.discover_streams()` in `tap_absorb/tap.py`
4. Add the stream to `select` in `meltano.yml`

---

## Submitting to MeltanoHub

To list `tap-absorb` on the [MeltanoHub](https://hub.meltano.com/extractors/):

1. Fork [https://github.com/meltano/hub](https://github.com/meltano/hub)
2. Copy `hub_submission.yml` from this repo to `_data/meltano/extractors/tap-absorb/<your-variant>.yml`
3. Update `variant`, `repo`, `pip_url`, and `logo_url` in the file
4. Open a pull request

See the [MeltanoHub contribution guide](https://hub.meltano.com/add-a-tap) for full instructions.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

## Looking for Help?

- Open an [issue](https://github.com/kashif-se/tap-absorb/issues)
- Join the [Meltano Slack](https://meltano.com/slack) and ask in `#plugins-general`
- Review [Absorb API docs](https://docs.myabsorb.com/integration-api/v2/docs)
