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

### Changed

- API contract: `vlm_aciklama`, `anahtar_kelimeler` and maximum lengths from the annotation guide; single-labeled memes get a reviewer check before gold (ADR-0009); `POST /memes/ai-drafts`, `vlm_taslak` and `on_doldurma` for AI drafts (ADR-0010).

### Fixed

- Annotation form: the new fields, inactive labels, clearing field confidence and opening the next item after a skip.
