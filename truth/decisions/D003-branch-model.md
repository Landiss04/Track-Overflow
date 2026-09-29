# D003-branch-model

**Status:** current
**Owner:** Kevin
**Provenance:** asserted by Kevin 2026-09-29
**Aliases:** branch model, default branch, release branch, integration branch
**Last updated:** 2026-09-29

## Context

The repository has two long-lived code branches, `development` and `main`. The agent
rules referred to "the development branch" without saying which branch is the trunk,
and the `truth/_inbox/` scaffold exists only on `development`.

## Decision

- `development` is the default branch. Feature branches are cut from it and merge back
  into it.
- `main` is release-only. No feature work happens on it and no branch is cut from it.

## Consequences

- `AGENTS.md` and the `truth/` scaffold live on `development`, so every feature branch
  inherits them. `main` does not carry them.
- The `truth` branch is separate from both and is never merged into either.
