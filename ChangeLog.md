# Change Log

## 2026-09-29

- Added the Shrubberies submission links and jury access cards to `/hackaton/`. Added copy controls. Kept deployed credentials outside public source files. Excluded the page and presentation from crawling, indexing, sitemap, and public navigation. Added anonymous presentation routing and credential-page cache controls.

- Added public Russian and English marketing pages for the deployed product. Added canonical and language URLs, social metadata, `WebApplication` structured data, a sitemap, crawler rules, a favicon, a web manifest, and a 1200 by 630 share image. Moved canonical trainer routes under `/app/*`. Added non-indexing rules, legacy redirects, immutable asset caching, real public 404 behavior, route tests, SEO contract tests, and DR-53. Preserved the private trainer and API admission boundary.
- Set explicit `application/xml` and `application/manifest+json` response types in the public Caddy template. This keeps the sitemap and web manifest usable when `X-Content-Type-Options: nosniff` is active.

## 2026-09-28

- Standardized the product brand as uppercase `ALOLA`. Removed the remaining previous-brand text from the Web UI and public release materials. Renamed the release presentation and PDF artifacts.
- Replaced the previous visible Web UI brand with `ALOLA`. Updated the Russian and English browser titles, header brand, metadata fallback, tests, and public README.
- Separated the public product repository from private plans and release-control tooling. The public `scripts/` directory now contains runtime launchers only.
- Prepared the template-only release candidate for Task 9.
- Added parser safety regressions for term complaints, contrast-clause proposals, third-party numbers, conditional trades, interest questions, insult boundaries, and explicit exits.
- Added persistent non-terminating training clarification recovery and truthful below-threshold review behavior.
- Added a pinned retry journey, portable startup, release gates, a stand runbook, screenshots, a template deck, a PDF, and a video script.
- Added fail-closed link, tag, bundle-content, and external-manifest release checks.
- Updated the frontend test dependency after an audit and added an audit gate.
- No external model request is required for the release path.
