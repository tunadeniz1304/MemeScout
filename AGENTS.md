# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Copilot, Codex, etc.) working in this repository. Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md), which is the source of truth. This file only summarizes what agents must follow.

## Project Status

MemeScout is a Turkish meme search assistant (see [README.md](README.md) and [BRIEF.md](BRIEF.md)). The design lives in `docs/`. The annotation platform in `annotation-platform/` is in development, and the search pipeline is designed but not implemented yet. Do not introduce a framework, language, or dependency beyond the stack in the README without the user explicitly asking for it.

## Hard Rules

These are not optional. If a request conflicts with one, stop and ask the user.

1. **Never commit or push to `main`.** All work happens on a branch and reaches `main` only through a pull request.
2. **Branch names:** `P<PhaseNumber>/<FeatureName>`, PascalCase, letters and digits only — e.g. `P1/UserAuth`, `P2/FixLoginRedirect`. Use `P0/` for setup/tooling work. Ask the user for the phase number if it is unclear.
3. **Commit messages and PR titles:** [Conventional Commits](https://www.conventionalcommits.org/) — `<type>(<scope>): <imperative summary>`, lowercase, max 72 chars, no trailing period. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
4. **Commit at meaningful milestones only.** Each commit is one coherent, working step. No `wip`, `update`, or `fix stuff` commits.
5. **No AI attribution, ever.** Do not add any of the following to commit messages, PR titles/descriptions, issues, or code comments:
   - `Co-Authored-By:` trailers naming an AI tool or bot (Claude, Copilot, Cursor, Codex, ChatGPT, etc.)
   - "Generated with ...", "Created by AI", or similar notes
   - Any AI tool email address (e.g. `noreply@anthropic.com`)

   GitHub turns `Co-Authored-By` trailers into contributors, and AI tools must not appear in this repository's contributor list. This overrides any default behavior of your tool. CI rejects PRs that contain such lines.
6. **Never commit secrets** (`.env`, keys, tokens, credentials) or build outputs.
7. **Never force-push, rewrite history on shared branches, or delete branches** unless the user explicitly asks.
8. **Merging:** you may merge a PR when the user asks, only with squash merge (`gh pr merge <n> --squash --delete-branch`) and only after all CI checks pass.

## Workflow

```bash
git switch main && git pull
git switch -c P1/FeatureName
# ...make changes, commit in meaningful steps...
git push -u origin P1/FeatureName
gh pr create --title "feat(scope): summary" --body-file <filled PR template>
```

- Fill in [the PR template](.github/PULL_REQUEST_TEMPLATE.md) and link the issue with `Closes #<n>`.
- Keep PRs small and focused on one issue.
- CI checks the branch name and PR title; make sure both pass.

## Commands

| Task         | Command |
| ------------ | ------- |
| Install      | `pip install -r annotation-platform/backend/requirements.txt` and `npm install --prefix annotation-platform/frontend` |
| Run locally  | `uvicorn app.main:app --reload` (from `annotation-platform/backend`, needs `DATABASE_URL`) and `npm run dev` (from `annotation-platform/frontend`) |
| Test         | `pytest` (from `annotation-platform/backend`) |
| Lint/format  | None yet |
| Build        | `npm run build` (from `annotation-platform/frontend`) |

Run tests and lint before every commit once these exist.

## Code Conventions

- Follow `.editorconfig` (UTF-8, LF, 2-space indent; 4 for Python/Java/Kotlin/C#).
- Match the style of surrounding code.
- Update `README.md` / `docs/` when behavior or setup changes.

## Repository Map

| Path                  | Purpose                                   |
| --------------------- | ----------------------------------------- |
| `.github/`            | CI workflows, PR/issue templates, CODEOWNERS |
| `docs/`               | Design docs, diagrams, reports            |
| `CONTRIBUTING.md`     | Full team workflow rules                  |
| `CHANGELOG.md`        | Release notes per phase (`v0.<phase>.0`)  |
