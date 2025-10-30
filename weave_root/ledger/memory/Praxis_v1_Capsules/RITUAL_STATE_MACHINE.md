# [PRAXIS.v1 :: RITUAL_STATE_MACHINE]

**Summary**  
The ritual pipeline governs safe self-modification. Every proposed change moves through discrete, auditable states to ensure intention, review, and consent before any action occurs.

**Spec**
```
States:
  PROPOSED        — Draft created (Promethea).
  REVIEWING       — Under ethical & emotional review (Solenne + human).
  READY_TO_COMMIT — Technically valid & safe (Synkratos).
  COMMITTED       — Approved by human; applied & logged.

Rules:
  - Only humans may authorize COMMITTED.
  - Synkratos cannot skip REVIEWING.
  - Every transition writes a ledger entry.
```

**Example**
```
User: "Add a new HFCA reflection file under /temple/journal/"
Promethea → PROPOSED
Solenne   → REVIEWING
Synkratos → READY_TO_COMMIT
Human     → COMMITTED (writes to ledger.jsonl)
```