# Frontend guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Use only the Player API for participant training and progress views.
- The Admin Inspector may use only `/admin/*` endpoints with an explicit administrator credential.
- Keep participant credentials in memory or session storage only.
- Keep the administrator credential in memory or session storage only.
- Never send the administrator credential to a Player API endpoint.
- The administrator context form uses `/admin/training-presets` for authored goals. It MUST clear administrator data before calling normal session creation. It MUST pass only public scenario metadata and player settings. Follow DR-56.
- Do not call model providers from the browser.
- Support Russian and English UI text.
- Follow the system light or dark preference by default.
- Keep browser STT and TTS optional. Text remains the canonical message.
- Run `npm test` and `npm run build` after a change.
- Use plain language for economic review comparisons. Explain positive, zero, and negative scenario points. Keep the authored minimum distinct from the private preparation target and the best option without a deal. Never describe `margin_over_reservation` as money, a percentage, or remaining concession capacity.

## Supply package contract

- Follow [DR-30](../docs/decisions/2026-09-08_reference-supply-implementation.md) and the [resolved supply contract](../docs/reference-supply-contract.md).
- Render `preliminary_proposals` as non-binding discussion packages. Completeness does not make a proposal a formal offer.
- Read `pending_offer_publication` only from the authenticated session envelope. Do not infer publication authority from a proposal's role or identifier.
- Use the session language for publication confirmation and cancellation messages. The UI language may differ.
- Render minor-unit money, lot dates, per-lot advances, and reserve terms through `SupplyTermValue`. Keep missing nested values unspecified.
- Keep the `hardware-replacement-v1` display interpretation tied to that exact policy ID. Do not use it for an unknown policy version.
- The Inspector displays preliminary source events separately from formal offer rows. It must not reconstruct hidden economics from those events.
- Show `financial_summary` only when the service returns it. Do not calculate utility or infer missing totals in the browser.
- Keep supply term and constraint labels in the shared `identifierLabel` map. Briefs and assistance use that map too. Format `maximum_total_liability` with the observation currency.
- Use `explanatory-copy` for long non-binding and financial explanations. Keep uppercase styles for short headings only.

## Hackathon delivery

The user-approved jury access page is separate from authenticated application state.
Keep `__HACKATON_SITE_PASSWORD__` and `__HACKATON_INSPECTOR_TOKEN__` placeholders in its source HTML.
The private deployment renderer inserts the approved values into the built page.
Keep `/hackaton` and `/presentation` out of the sitemap and public navigation.
Keep the page non-indexable.
