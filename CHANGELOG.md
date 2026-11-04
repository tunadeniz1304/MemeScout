# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Each development phase `P<n>` is released as `v0.<n>.0`.

## [Unreleased]

### Added

- Repository setup: license, README template, contribution guidelines, PR/issue templates, and PR checks.
- Annotation API: every operation in `annotation-platform/openapi.yaml`, with blind labeling, the reviewer and leakage rules, versioned label lists, review and gold records, agreement statistics, the audit log and JSONL export.
- Meme images stored in PostgreSQL and a script that imports memes from WhatsApp exports through the API.
- AI drafts (ADR-0010): LLM cards prefill the form of single-labeled memes, are kept unchanged for comparison, and are imported from YAML or CSV with a script.
- Exclusion vote and pool (ADR-0011): a "Bu mem kullanılmasın" vote with a reason and an optional note on the labeling screen, and an admin "Havuz" page to keep or exclude the voted memes. Excluded memes drop out of queues, assignments, review, agreement, exports and test-query answers until the admin keeps them again.
- Automatic reassignment (ADR-0013): a meme skipped in the main round goes to the eligible annotator with the fewest open items, and falls into the exclusion pool when nobody is left. A single-labeled meme first submitted with familiarity 3 also goes to a second annotator, except AI-draft memes.

### Changed

- API contract: `vlm_aciklama`, `anahtar_kelimeler` and maximum lengths from the annotation guide; single-labeled memes get a reviewer check before gold (ADR-0009); `POST /memes/ai-drafts`, `vlm_taslak` and `on_doldurma` for AI drafts (ADR-0010); exclusion vote and pool operations, the `cikarildi` meme status, `MEME_CIKARILDI` and `HAVUZDA_DEGIL` errors and `cikarilan` in progress stats (ADR-0011).

### Fixed

- Annotation form: the new fields, inactive labels, clearing field confidence and opening the next item after a skip.
- Annotation screen: when no item is open but the queue still has work, it offers the next item instead of saying everything is done.
