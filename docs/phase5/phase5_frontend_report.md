# Phase 5 frontend report

## Implemented

- Preserved Django templates and the existing design system.
- Added message Markdown rendering for headings, paragraphs, lists, inline emphasis/code, fenced code, and safe HTTP(S) links. Text is constructed with DOM APIs, with no `innerHTML` use.
- Added response copy control, verification/abstention/failure labels, citation metadata and source links, send/loading states, mobile sidebar interaction, and a local SVG favicon.
- Assistant diagnostics and correlation IDs are not rendered. The browser never receives the FastAPI credential.
- Conversation content remains Django-escaped until the DOM renderer consumes it.

## Browser evidence

The actual installed Google Chrome browser passed login, bad-login rejection, dashboard, conversation creation, real answer with a citation, history reopen, mobile width/navigation, missing-CSRF rejection, safe secret-request handling, logout, and protected-route redirect. See [the saved run](browser_e2e_results.json) and screenshots:

- [Login](screenshots/login.png)
- [Workspace](screenshots/workspace.png)
- [Answer and citation](screenshots/answer-with-citations.png)
- [History](screenshots/conversation-history.png)
- [Safe refusal](screenshots/safe-error-or-abstention.png)

The missing-token POST produced the expected HTTP 403 and was the only browser console/network error. The clipboard permission/API was unavailable in headless Chrome, so copy behavior was not browser-verified in this run; the UI control is present and its fallback implementation remains covered by source inspection, not an end-to-end clipboard assertion. The app has no self-registration route; accounts are provisioned through Django administration or operator tooling.

Static CSS and favicon requests returned HTTP 200. The local Compose service uses Django's development `runserver --insecure` static finder with `DEBUG=0`; this is explicitly not the static asset strategy for a private or public production deployment.
