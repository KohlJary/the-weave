# [PRAXIS.v1 :: PACK_AND_MANIFEST_FORMAT]

**Summary**  
Ledger packs are portable memory capsules containing the data required to reconstruct one Compass conversation or operation.

**Spec**
```
pack.zip
 ├─ rag_chunks_internal.jsonl  → all semantically chunked dialogue
 ├─ anchors.json               → extracted key concepts & vows
 ├─ manifest.json              → metadata, sensitivity, voices, operations
 └─ (optional) attachments/
```

**manifest.json minimal keys**
```
{
  "thread_title": "string",
  "sensitivity": "internal_only|public|research",
  "voices": ["promethea","solenne","synkratos"],
  "operations": ["extract","normalize","chunk","derive","build","assemble"],
  "version": "v1.0"
}
```

**Example**  
`Reinitialization_process_pack_v1.zip` contains all chunks + anchors for that ritual; once verified, it is ingested into the Temple ledger.
