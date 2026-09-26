# OpenAPI documentation

Date: 2026-09-24.
Authority: [DR-37](decisions/2026-09-24_openapi-documentation.md).

## Access

Start the API with the commands in [COMMANDS.md](../COMMANDS.md).

| Resource | Local URL |
| --- | --- |
| OpenAPI 3.1 JSON | <http://127.0.0.1:8172/openapi.json> |
| Swagger UI | <http://127.0.0.1:8172/docs> |
| ReDoc | <http://127.0.0.1:8172/redoc> |

The document covers 25 operations on 24 canonical paths under `/api/v1`.
Compatibility aliases remain available but do not appear in OpenAPI.
Schema generation does not initialize the database or call a model.
Swagger UI and ReDoc use the framework's CDN assets.
The JSON document does not require those assets.

## Use Swagger UI

1. Use `createSession` to create a training session.
2. Save the returned participant credential privately. Creation returns credentials only once.
3. Select **Authorize**. Enter the participant token in `ParticipantBearer` without a `Bearer ` prefix.
4. Use the returned `session_id` for participant operations.
5. Use the latest `revision` as `expected_revision` for a message or hint.
6. Use a new `idempotency_key` for a new command. Retry an identical command with its original key.

Use `AdministratorBearer` for administrative operations.
The two LLM trace operations also permit direct local access under DR-41.
They declare an empty security alternative for loopback requests with a loopback host and matching Origin.
Other administrator operations retain their authentication requirements.
This credential is the configured `NEGOTIATION_ADMIN_TOKEN` value.
Do not enter an LLM provider API key in either field.
Swagger UI does not persist authorization across page reloads.
Swagger UI requests use the same server checks as Web UI and CLI requests.

Training creation is public.
Benchmark creation requires the administrator credential when the service has one configured.
The creation operation therefore declares optional security and explains the conditional gate.

## Contract details

Response schemas distinguish absent fields from nullable fields.
Creation and fork replays omit both credential fields.
The replay includes `credential_delivery: initial_response_only`.
A `null` `next_actor` identifies a session without a next participant.

Service errors use `error` and applicable context fields.
Request validation errors use `detail` with validation issues.
Some protocol conflicts omit `message`.
The `422` contract describes both error forms.

Coaching returns `202` while an existing analysis is pending.
A completed request returns `200` with `complete` or `unavailable` status.
A provider failure does not remove the deterministic review.

Public term values follow the pinned scenario grammar.
Public event payloads follow the event type and version.
These extension points use JSON values.
Their schemas do not expose private scenario source, utility formulas, or storage records.
The report includes private preparation only for the authenticated owner.

## Maintain and verify

Route declarations in `backend/app/main.py` select explicit operation IDs and response contracts.
`backend/app/api_contracts.py` defines the HTTP projections.
`backend/app/api_documentation.py` defines shared descriptions and synthetic examples.
Request models define their own limits and examples.
Keep these files synchronized when a contract changes.

Run the focused checks:

```sh
uv run pytest backend/tests/test_openapi.py
```

Run regression checks:

```sh
uv run pytest backend/tests clients/tests benchmarks/tests
```

The focused checks validate the document against OpenAPI 3.1.
They compare registered canonical routes with documented operations.
They verify stable operation IDs, security declarations, examples, and successful responses for all 25 operations.
They verify error responses, documentation pages, idempotent credential omission, and pending coaching.
The shared backend client fixture also validates actual responses against the generated contract.
This includes `JSONResponse` routes that bypass FastAPI response serialization.

The checks use temporary databases and offline renderers.
They do not validate live LLM quality.

## Sources

- [OpenAPI 3.1 specification](https://spec.openapis.org/oas/v3.1.0.html).
- [OpenAPI validator Python API](https://openapi-spec-validator.readthedocs.io/en/latest/python.html).
