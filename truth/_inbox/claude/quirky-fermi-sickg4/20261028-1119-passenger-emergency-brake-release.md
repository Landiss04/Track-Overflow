**Target:** truth/arbitration/passenger-emergency-brake.md
**Action:** replace
**Proposed by:** Claude on claude/quirky-fermi-sickg4
**Provenance:** asserted by Kevin Schillinger 2026-10-28, in chat: "it is latched until the train controller sends ebreak = false"; the rest of the entry unchanged from origin/truth

---

# passenger-emergency-brake

**Status:** current
**Owner:** Train Model
**Provenance:** `Train_Model_Backend_Design.pdf` §5.8 (Locked) and Interfaces table, supplied by Kevin Schillinger 2026-09-30; brake failure blocking only the service brake clarified by the course instructor and relayed by Kevin Schillinger 2026-10-02; release by the Train Controller asserted by Kevin Schillinger 2026-10-02; release when the Train Controller sends emergency brake false asserted by Kevin Schillinger 2026-10-28
**Aliases:** passenger e-brake, passenger emergency brake pull, emergency brake ownership
**Last updated:** 2026-10-28

## Definition

The Train Model owns the passenger emergency brake. Pulling it makes the Train Model
apply the emergency brake force. The Train Model reports Emergency Brake State to the
Train Controller, and that state is active when either the Train Controller's emergency
brake command or a passenger pull is active. A brake failure does not disable it.

The Train Controller releases the emergency brake. A passenger pull stays latched until
the Train Controller sends emergency brake false
([emergency-brake-command](../signals/emergency-brake-command.md)). The Train Model UI
offers no release control (D011).

## Notes

- Brake failure blocks the service brake only, so a passenger pull still applies the
  emergency brake. See `modules/train-model.md` `## Failure modes`.
- There is no separate release command;
  [passenger-brake-release](../signals/passenger-brake-release.md) is withdrawn.

## Supersedes

- Release mechanism: previously the one-shot passenger-brake-release command (Kevin
  Schillinger 2026-10-20); now the pull is latched until the Train Controller sends
  emergency brake false (Kevin Schillinger 2026-10-28).
