# MemeScout frontend

Vite + React client for the MemeScout annotation API.

## Run locally

```bash
npm install
npm run dev
```

The client uses `http://127.0.0.1:8000/api/v1` by default. Copy `.env.example` to `.env.local` to set `VITE_API_BASE_URL` to another API base URL.

The annotation form and label options load from `GET /schema/annotation` and `GET /label-lists`. The API service in `src/services/api.js` maps every path and method in `../openapi.yaml`, including auth, users, memes, assignments, annotations, comments, reviews, test queries, statistics, audit, recheck and export. JSON errors are exposed as `ApiError` with the contract's error code, field paths and details.

`src/services/contracts.js` contains the API enum values, request payload shapes and client feedback validation derived from the schema response. The server remains authoritative for submission validation, role permissions and state changes.

## Privacy and annotation rules

- The annotation view requests only the current user's queue, own annotation, image, and comments. It does not request the other annotator's annotation or gold record.
- Meme comments are displayed from the blind-rule-filtered `GET /memes/{meme_id}/comments` response. Before the current annotation is submitted, the UI also filters double-label comments to those written by the signed-in user.
- The test-query screen lists only queries written by the signed-in user. Candidate gold memes are checked before submission against the current user's own annotation summaries and the gold reviewer. It never loads another annotator's private annotation content. If the check is inconclusive, it blocks the candidate. `POST /test-queries` remains the final leakage check and any `SIZINTI` response is shown with the offending meme IDs.
- A reviewer cannot approve a meme they annotated; the API's `REVIEWER_ANNOTATOR_OLAMAZ` response is surfaced to the user.
- Familiarity 1–2 is blocked from submission and can be skipped for reassignment. Field confidence values (1–3) are included only when selected.
- Drafts use optimistic `surum` updates, save periodically and on page exit, and send focused active time capped at 300 seconds per request. Validation errors are associated with their OpenAPI field paths.

Keyboard shortcuts in the annotation screen: **Ctrl/Cmd+S** saves, **Ctrl/Cmd+Enter** submits, and **Alt+→** saves and opens the next queued item.
