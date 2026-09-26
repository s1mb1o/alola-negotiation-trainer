# DR-37. Required OpenAPI documentation

Date: 2026-09-24.
Status: accepted and implemented at the user's request.

## Decision

The service MUST publish an OpenAPI 3.1 document at `/openapi.json`.
The service MUST provide interactive Swagger UI documentation at `/docs`.
The service MAY provide ReDoc at `/redoc`.
The documentation MUST cover every implemented canonical REST operation under `/api/v1`.
Compatibility aliases MAY remain excluded from the schema.
Planned operations MUST NOT appear as implemented operations.

Each operation MUST have a unique, stable `operationId`, a summary, and a description.
The document MUST describe path, query, and header parameters.
The document MUST describe request bodies and successful response bodies.
The document MUST describe applicable error status codes and error bodies.
Schemas MUST identify required fields, optional fields, nullable values, enums, and validation limits.
Protected operations MUST declare their authentication scheme and security requirement.
Descriptions MUST state actor access restrictions and disclosure rules.
Applicable descriptions MUST explain idempotency, revision checks, and binding confirmation.
Representative request and response examples MUST use synthetic data.
Examples MUST NOT contain real credentials or hidden session state.
Swagger UI requests MUST use the same authentication, authorization, and validation as other clients.

The service MUST generate the document from route declarations and typed API contracts.
Each API contract change MUST update the schema and its relevant examples in the same change.
Automated checks MUST validate the document against its declared OpenAPI version.
Automated checks MUST verify canonical operation coverage and unique `operationId` values.
Contract tests MUST verify representative successful and error responses against the documented schemas.
Documentation availability alone MUST NOT count as contract completeness.

## Options and rationale

1. Keep prose documentation only. This has low maintenance cost. Clients cannot consume a machine-readable contract.
2. Maintain a separate handwritten OpenAPI document. This permits full control. The document can diverge from the implementation.
3. Generate OpenAPI from route declarations and typed contracts. This uses the existing FastAPI service. Contract checks are still necessary.

Selected option: 3.
The service already generates OpenAPI.
The requirement adds explicit coverage, maintenance, and acceptance rules.

## Acceptance and current status

The release MUST serve a valid document and usable Swagger UI.
The release MUST satisfy the operation, schema, security, and example requirements above.
The [API specification](../api.md), [architecture](../architecture.md), [product requirements](../product.md), and [MVP plan](../mvp.md) carry this requirement.

The initial inspection found 20 canonical paths and 21 operations.
It found no `securitySchemes` entries and 11 empty successful-response schemas.

The implementation now publishes OpenAPI `3.1.0`, Swagger UI, and ReDoc.
All 21 operations have explicit operation IDs, descriptions, and typed response contracts.
Protected operations declare participant or administrator Bearer security.
Creation documents its conditional administrator gate for benchmark mode.
Error contracts include both service errors and request validation errors.
Examples contain authored synthetic data.
Generation preserves explicit nulls in response examples.

The focused suite validates the document, canonical route coverage, stable operation IDs, security, and examples.
It validates successful HTTP responses for all 21 operations.
It also checks authentication failures, error shapes, credential omission on replay, and pending coaching.
The shared backend client fixture validates real response bodies against the generated schemas.
See the [OpenAPI guide](../openapi-guide.md) and [implementation plan](../plans/07_openapi-contracts.md).

## Consequences and risks

API changes require corresponding schema updates.
Automatic generation does not establish response accuracy.
Contract tests must detect differences between documented and actual responses.
Examples require the same disclosure review as other public documentation.
