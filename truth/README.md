# truth/

The source-of-truth store. It lives on the `truth` branch and holds normative facts
only — interfaces, signals, arbitration rules, conventions, decisions — never status.
Start at [`INDEX.md`](INDEX.md).

Agents read it without checking it out:

```
git fetch origin truth
git show origin/truth:truth/INDEX.md
```

Agents never write here. Proposals go to `truth/_inbox/<branch>/` on feature branches
cut from development. Promotion onto this branch is human-only.

Full rules: [`AGENTS.md`](../AGENTS.md).
