# Frontend guide

Read [`../CLAUDE.md`](../CLAUDE.md) and [`../AGENTS.md`](../AGENTS.md) first.

- Use only the Player API for participant training and progress views.
- The Admin Inspector may use only `/admin/*` endpoints with an explicit administrator credential.
- Keep participant credentials in memory or session storage only.
- Keep the administrator credential in memory or session storage only.
- Never send the administrator credential to a Player API endpoint.
- Do not call model providers from the browser.
- Support Russian and English UI text.
- Follow the system light or dark preference by default.
- Keep browser STT and TTS optional. Text remains the canonical message.
- Run `npm test` and `npm run build` after a change.

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
