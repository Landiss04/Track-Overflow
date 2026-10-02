# truth/

Normative facts live on the `truth` branch. They are not present in this directory.

```
git fetch origin truth
git ls-tree -r --name-only origin/truth -- truth/
git grep <pattern> origin/truth -- truth/
git show origin/truth:truth/<path>
```

This directory is write-only. It is used for proposals, in `_inbox/<branch>/`.

Promotion of a proposal onto the `truth` branch is human-only.

See the Source of Truth section of [`AGENTS.md`](../AGENTS.md).
