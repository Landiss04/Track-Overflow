Promotion runbook — truth branch
Human procedure. Not for agents. Agents never perform any step in this document.

Floor is weekly, Wednesday. It is a floor, not a gate: a shared-interface fact that blocks another module owner goes out of band the same day, by message, and gets promoted whenever you next sweep. The sweep catches what is not urgent; it does not batch what is. Each run promotes one feature branch; a sweep is one run per branch with pending proposals.

Substitute the name of the source feature branch for <dev> throughout.

1. Collect
git fetch origin
git ls-tree -r --name-only origin/<dev> -- truth/_inbox/<dev>/
Every .md file listed is a pending proposal from <dev>. Files under other _inbox/ directories on that branch were inherited from another branch and are not promoted from here.

Read each one without checking anything out:

git show origin/<dev>:truth/_inbox/<dev>/<file>
2. Check against the promotion log
Before reviewing content, check each proposal filename against the log on the truth branch:

git show origin/truth:truth/_promotions.md
A proposal already listed there is a resurrection — it was promoted and deleted, but a feature branch cut before the deletion still contained the file and reintroduced it on merge. Delete it in step 5 without re-reviewing. Do not promote it again.

3. Decide
For each remaining proposal, one of:

Promote — the fact is correct and belongs in the store.
Modify then promote — the fact is right but the entry needs editing. Edit at promotion time; the proposal is not the artifact of record.
Deny — the fact is wrong, redundant, or not normative. Status and progress claims are always denied; they belong in the repo, not the store.
Hold — needs another module owner's agreement before it can be asserted. Leave it in the inbox and message the owner. Do not promote a contested shared-interface fact unilaterally.
Judgement calls that cannot be delegated: whether the fact is module-internal or touches a shared interface, and whether it conflicts with something already in the store. Both need project context and arbitration authority.

4. Promote
You no longer place entries at their canonical paths. You put each promoted proposal, wrapper and all, into truth/incoming/. After the PR merges, the truth-incoming workflow (.github/workflows/truth-incoming.yml) moves each entry to its **Target:** path.

Use an ephemeral detached worktree so nothing on disk persists and your primary worktree's branch never changes.

git fetch origin truth
git worktree add --detach /tmp/truth-promote origin/truth
cd /tmp/truth-promote
git switch -c promote-YYYYMMDD
Stage each promoted proposal:

Copy the proposal file as-is, wrapper included, to truth/incoming/<dev>/<proposal-filename>:
mkdir -p truth/incoming/<dev>
git show origin/<dev>:truth/_inbox/<dev>/<file> > truth/incoming/<dev>/<file>
Check the wrapper's **Target:** and **Action:** lines. The workflow trusts them. create requires the target not to exist yet. replace requires it to exist, and overwrites it with the entry below the ---.
To modify, edit the entry below the ---. Everything below that line is written to the target verbatim.
If it supersedes an existing entry, use replace. Make the entry the full current value with a ## Supersedes section naming the previous value and why it changed. Keep only the current value — git holds the history.
If it conflicts with an existing entry and both sources are credible, keep both in a ## Conflict section with provenance for each and a named resolution owner.
Confirm required fields are present. An entry without provenance does not go in. The workflow also refuses one.
Check the new entry's key and aliases against existing keys and aliases in that shard. Two names for the same thing is the failure this catches.
Update truth/INDEX.md in the same PR — the shard's last-changed date, and a new row for a new shard or decision.
Append one line per promoted proposal to truth/_promotions.md:

| YYYY-MM-DD | <dev> | <proposal-filename> | <canonical-path> | promoted |
Log denials the same way with denied and a short reason. A denied proposal that isn't logged will be re-proposed by the next agent that rediscovers the fact.

Then:

git add -A && git commit -m "promote: <summary> (sweep YYYY-MM-DD)"
git push -u origin promote-YYYYMMDD
Open a PR against truth. Self-merge is acceptable for module-internal facts. Shared-interface facts need the affected module owner as reviewer.

After it merges, check the truth-incoming run in the Actions tab:

Green: the entries are at their canonical paths, truth/incoming/ holds only .gitkeep, and a promote: move truth/incoming/ ... commit follows your merge.
Red: nothing moved. The log names each bad file and why. Fix the file in truth/incoming/ with a follow-up PR; the workflow reruns when it merges.
5. Clean up
After the workflow has moved the entries, delete the promoted and denied proposals from <dev>. Held proposals stay.

Commit the deletion directly on <dev>, not in the promote worktree. Tell the branch owner first; they may have work in progress on it.

git rm truth/_inbox/<dev>/<file>
If <dev> has already been merged into development, the proposals are there too. Delete them from development as well, on a normal branch off development, or they will resurrect into every branch cut from it.

Never delete truth/_inbox/.gitkeep or truth/README.md. They are the scaffold that makes the inbox inherit into new branches; removing them breaks proposal writing on every branch created afterward, and the breakage won't surface until an agent has nowhere to write.

Remove the worktree:

cd ~/Trains/trains
git worktree remove /tmp/truth-promote
6. Announce
Post what changed to the team channel — entry paths and one line each. A fact that exists in the store but that nobody knows landed is a fact that keeps getting re-derived.

If the sweep is skipped
Fallback is the PR checklist: a PR that adds files under truth/_inbox/ is a PR whose proposals need promoting. The reviewer's job is to notice. A PR into development should arrive with its own truth/_inbox/<branch>/ already promoted and empty. This and the weekly sweep are both load-bearing, not redundant — promotion depends entirely on a human doing it, so there are deliberately two places it can be caught.
