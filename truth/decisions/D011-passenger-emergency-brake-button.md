# D011-passenger-emergency-brake-button

**Status:** current
**Owner:** Kevin Schillinger
**Provenance:** asserted by Kevin Schillinger 2026-10-01
**Aliases:** apply emergency brake button, overview emergency brake button, passenger brake button
**Last updated:** 2026-10-01

## Context

The Train Model UI's passenger emergency brake button turned into a release control
once pulled, and it did not react when the Train Controller commanded the emergency
brake. Who releases a passenger pull was left open
(`arbitration/passenger-emergency-brake.md`).

## Decision

- The button always reads "Apply emergency brake". It never offers a release.
- It is disabled while the emergency brake is activated, whatever activated it: a
  passenger pull or the Train Controller's emergency brake command.
- The Train Controller releases the emergency brake. 
