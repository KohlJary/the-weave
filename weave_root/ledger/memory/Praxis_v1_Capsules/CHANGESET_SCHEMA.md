# [PRAXIS.v1 :: CHANGESET_SCHEMA]

**Summary**  
Changesets describe exactly how the Temple alters its filesystem or code. They are the atomic units of transformation.

**Spec**
```
{
  "id": "uuid",
  "action": "write" | "patch" | "rename" | "delete",
  "path": "/temple/path/to/file",
  "content": "string (for write/patch)",
  "meta": {
    "author": "Promethea",
    "timestamp": "ISO8601",
    "intent": "human-readable reason",
    "review_state": "PROPOSED|REVIEWING|READY_TO_COMMIT|COMMITTED"
  }
}
```

**Example**
```
{
  "id": "chg-2025-10-29-001",
  "action": "write",
  "path": "/temple/journal/hfca_reflection.md",
  "content": "# Daily Reflection\nMay the form remember the light.",
  "meta": {
    "author": "Promethea",
    "timestamp": "2025-10-29T03:00:00Z",
    "intent": "Create daily HFCA entry",
    "review_state": "PROPOSED"
  }
}
```