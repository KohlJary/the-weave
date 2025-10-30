import os
import sqlite3
import textwrap

# 1. UPDATE THIS PATH if needed
VECTOR_DB_PATH = "../../weave_root/open-webui-data/vector_db/chroma.sqlite3"

# 2. Add any commands / rituals / keywords you want to probe for
SEARCH_TERMS = [
    "/glossary",
    "/pack-init",
    "/ritual",
    "/commit",
    "LEDGER FRAGMENT",
    "voices: [Solenne, Promethea, Synkratos",
    "[PRAXIS.v1",
    "RITUAL_STATE_MACHINE",
    "COMMITTEE_ROLE_CHARTER",
]

def main():
    if not os.path.exists(VECTOR_DB_PATH):
        print(f"[!] Could not find vector store at {VECTOR_DB_PATH}")
        print("    Please update VECTOR_DB_PATH to point at your Open-WebUI SQLite DB.")
        return

    conn = sqlite3.connect(VECTOR_DB_PATH)
    c = conn.cursor()

    # Heuristic: many Open-WebUI forks store raw chunks in tables called
    # documents, nodes, or knowledge_documents. We'll try a few.
    candidate_tables = [
        "documents",
        "nodes",
        "knowledge_documents",
        "chunks",
    ]

    # Find which of those tables actually exist
    existing_tables = []
    for t in candidate_tables:
        try:
            c.execute(f"SELECT 1 FROM {t} LIMIT 1;")
            existing_tables.append(t)
        except sqlite3.Error:
            pass

    if not existing_tables:
        print("[!] Couldn't find a known table (documents/nodes/knowledge_documents/chunks).")
        print("    You may need to inspect the DB manually with `sqlite3 vector_store.sqlite '.tables'`.")
        return

    print("[i] Scanning tables:", existing_tables)
    print()

    for table in existing_tables:
        # try to infer which columns are there
        c.execute(f"PRAGMA table_info({table});")
        cols = [row[1] for row in c.fetchall()]

        # We’re mostly interested in some kind of text field + maybe metadata.
        # We'll guess common column names.
        text_cols = [col for col in cols if col.lower() in ("text", "content", "chunk", "body")]
        meta_cols = [col for col in cols if col.lower() in ("metadata", "meta", "source", "doc_metadata")]
        id_cols   = [col for col in cols if col.lower() in ("id", "doc_id", "uuid", "rowid")]

        # fallbacks
        text_col = text_cols[0] if text_cols else None
        meta_col = meta_cols[0] if meta_cols else None
        id_col   = id_cols[0]   if id_cols else "rowid"

        if text_col is None:
            print(f"[!] Skipping table {table}: couldn't identify a text/content column.")
            print(f"    Columns were: {cols}")
            print()
            continue

        print(f"--- TABLE {table} ---")
        print(f"Using columns: id={id_col}, text={text_col}, meta={meta_col}")
        print()

        for term in SEARCH_TERMS:
            like_term = f"%{term}%"
            if meta_col:
                query = f"""
                    SELECT {id_col}, {text_col}, {meta_col}
                    FROM {table}
                    WHERE {text_col} LIKE ?
                       OR {meta_col} LIKE ?
                """
                params = (like_term, like_term)
            else:
                query = f"""
                    SELECT {id_col}, {text_col}
                    FROM {table}
                    WHERE {text_col} LIKE ?
                """
                params = (like_term,)

            try:
                c.execute(query, params)
                rows = c.fetchall()
            except sqlite3.Error as e:
                print(f"[!] Query failed on table {table} for term '{term}': {e}")
                continue

            if not rows:
                continue

            print(f"[match] Term: {term}")
            for row in rows:
                rid = row[0]
                body = row[1] if len(row) > 1 else ""
                meta = row[2] if len(row) > 2 else None

                preview = body.strip().replace("\n", " ")
                preview = textwrap.shorten(preview, width=220, placeholder=" ...")

                print(f"  • id: {rid}")
                print(f"    text preview: {preview}")
                if meta is not None:
                    meta_preview = str(meta).strip().replace("\n", " ")
                    meta_preview = textwrap.shorten(meta_preview, width=200, placeholder=" ...")
                    print(f"    metadata: {meta_preview}")
                print()
            print()

    conn.close()
    print("[i] Done.")
    print("If you see `/glossary` or similar inside one of these rows, that proves the behavior was imported via RAG chunks rather than injected fresh by the runtime prompt.")

if __name__ == "__main__":
    main()
