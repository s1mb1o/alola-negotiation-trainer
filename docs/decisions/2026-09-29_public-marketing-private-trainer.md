# DR-53. Public marketing pages and private trainer

Date: 2026-09-29.
Status: accepted at the user's request.

## Decision

The deployment MUST publish a Russian marketing page at `/ru/`.
The deployment MUST publish an English marketing page at `/en/`.
The deployment MUST publish a Russian hackathon landing page at `/hackaton/`.
The hackathon page MUST identify the team as `Shrubberies`.
The page MUST show the submitted repository, documentation, presentation, prototype, additional-materials, and landing URLs.
The page MUST show the user-approved jury username, password, and inspector Bearer token.
The deployment MUST insert those two secret values from its environment into the built HTML.
The public repository MUST contain placeholders instead of the secret values.
The `/hackaton` redirect, `/hackaton/*` files, and `/presentation` MUST work without Basic Authentication.
The page MUST declare `noindex, nofollow, noarchive, nosnippet`.
The deployment MUST send the same `X-Robots-Tag` value and `Cache-Control: no-store` for these routes.
The page MUST use the `no-referrer` policy.
The `robots.txt` file MUST disallow `/hackaton` and `/presentation`.
The sitemap and public navigation MUST NOT link to these routes.
Crawler controls do not enforce access control. Anyone with the URL can read the page.
The `/presentation` route MUST serve the approved presentation PDF.
The hackathon landing page MUST contain the project pitch, the verified demonstration path, the implemented architecture boundary, and project resource links.
The hackathon landing page MUST show approved screenshots of a recorded negotiation and its assessment.
The page MUST identify recorded scores as product scores from one demonstration run.
The page MUST NOT present these scores as independently validated skill measurements or learning improvement.
The page MUST provide an anonymous presentation download and explicit access instructions for protected resources.
Screenshot enlargement and manual theme selection MAY use progressive enhancement.
The pitch, screenshots, resource links, and system theme MUST remain usable without JavaScript.
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
The `/ru/` and `/en/` marketing pages MUST NOT expose a participant credential, administrator credential, hidden scenario state, or provider credential.
The user-approved hackathon credential block is a separate delivery surface.

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

The September 29 redesign uses the user-selected Nord Systems demonstration.
It replaces the previous hero's 26-to-70 branch comparison with recorded product evidence.
The selected screenshots MUST pass a privacy review before publication.
The public build MUST NOT include the private source report or its machine-readable recording.
The presentation and screenshots are static assets, not live session access.

The deployment configuration must distinguish public marketing paths from private application paths.
The availability canary must authenticate at a private trainer path.
The release verifier must test both public discovery and private application access.
Search engines can discover the marketing pages after their next crawl.
This change does not guarantee ranking or immediate indexation.
Public assets reveal compiled frontend code.
The source repository already treats this code as public product code.

## Acceptance

The production build MUST contain the two marketing pages and the hackathon landing page.
Automated checks MUST verify their language, metadata, structured data, headings, and links.
The release check MUST verify public discovery files and HTTP 404 behavior.
The release check MUST verify private trainer and bootstrap API access.
The release check MUST verify immutable caching for a content-hashed asset.
