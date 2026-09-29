# DR-53. Public marketing pages and private trainer

Date: 2026-09-29.
Status: accepted at the user's request.

## Decision

The deployment MUST publish a Russian marketing page at `/ru/`.
The deployment MUST publish an English marketing page at `/en/`.
The root path `/` MUST redirect to `/ru/`.
Each marketing page MUST contain useful HTML without JavaScript execution.
Each marketing page MUST define a unique title and description.
Each marketing page MUST define a canonical URL and reciprocal `hreflang` links.
Each marketing page MUST define Open Graph and Twitter metadata.
Each marketing page MUST define truthful `WebApplication` structured data.
The deployment MUST publish valid `robots.txt` and `sitemap.xml` files.
Unknown public paths MUST return HTTP 404.

The trainer MUST use the `/app/*` path namespace.
The canonical trainer routes are `/app/training`, `/app/progress`, and `/app/inspector`.
The previous trainer routes MUST redirect to the matching canonical route.
The trainer routes MUST retain the deployment admission control.
The trainer HTML MUST declare `noindex, nofollow`.
The deployment MUST also send an `X-Robots-Tag: noindex, nofollow` header for trainer and API responses.
The public marketing pages MUST NOT expose a participant credential, administrator credential, hidden scenario state, or provider credential.

Content-hashed frontend assets MAY be public.
The deployment SHOULD cache content-hashed assets for one year with `immutable`.
The marketing pages MUST follow the system light or dark preference.
The public page text MUST describe only implemented product behavior.
The public page text MUST NOT claim validated learning outcomes.

## Options and rationale

1. Keep the complete site behind HTTP Basic Authentication.
   This option preserves the existing boundary.
   Search crawlers cannot access any useful page.
2. Publish static marketing pages and keep the trainer private.
   This option gives search crawlers stable content and metadata.
   It preserves the paid-provider admission boundary.
3. Make the complete trainer anonymous.
   This option gives direct product access.
   It removes the current paid-provider admission control.

Selected option: 2.
The marketing surface does not need application state.
The trainer can retain its existing security controls.
Static HTML also removes JavaScript rendering as a discovery dependency.

## Consequences and risks

The deployment configuration must distinguish public marketing paths from private application paths.
The availability canary must authenticate at a private trainer path.
The release verifier must test both public discovery and private application access.
Search engines can discover the marketing pages after their next crawl.
This change does not guarantee ranking or immediate indexation.
Public assets reveal compiled frontend code.
The source repository already treats this code as public product code.

## Acceptance

The production build MUST contain both marketing pages.
Automated checks MUST verify their language, metadata, structured data, headings, and links.
The release check MUST verify public discovery files and HTTP 404 behavior.
The release check MUST verify private trainer and bootstrap API access.
The release check MUST verify immutable caching for a content-hashed asset.
