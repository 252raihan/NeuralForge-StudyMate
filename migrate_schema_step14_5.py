"""
NeuralForge StudyMate - Step 14.5A schema sync migration.

Upgrades an EXISTING database/studymate.db to match database/schema.sql for the
three Step 14.5 hardening additions:

  1. study_materials.content_hash TEXT
  2. unique partial index idx_study_materials_content_hash
  3. unique partial index idx_one_active_generated_attempt

Safe by design:
  - Idempotent: re-running is a no-op (column/index presence is detected first).
  - Non-destructive: never drops tables, columns or rows.
  - Refuses to create a unique index while duplicate data exists; reports the
    conflicting IDs instead of silently deleting or mutating records.

Run:  python migrate_schema_step14_5.py
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database" / "studymate.db"


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}


def migrate(db_path=DB_PATH):
    if not Path(db_path).is_file():
        print(f"[abort] database not found: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ok = True
    try:
        # 1. add content_hash column only if missing
        if "content_hash" not in _columns(conn, "study_materials"):
            conn.execute("ALTER TABLE study_materials ADD COLUMN content_hash TEXT")
            conn.commit()
            print("[ok] added column study_materials.content_hash")
        else:
            print("[skip] column study_materials.content_hash already present")

        # 2a. guard duplicate non-NULL content_hash before unique index
        if "idx_study_materials_content_hash" not in _indexes(conn, "study_materials"):
            dups = conn.execute(
                "SELECT content_hash, COUNT(*) AS n, GROUP_CONCAT(id) AS ids "
                "FROM study_materials WHERE content_hash IS NOT NULL "
                "GROUP BY content_hash HAVING COUNT(*) > 1"
            ).fetchall()
            if dups:
                ok = False
                print("[blocked] duplicate content_hash values prevent unique index:")
                for d in dups:
                    print(f"   hash={d['content_hash']} count={d['n']} material_ids={d['ids']}")
            else:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_study_materials_content_hash "
                    "ON study_materials(content_hash) WHERE content_hash IS NOT NULL"
                )
                conn.commit()
                print("[ok] created idx_study_materials_content_hash")
        else:
            print("[skip] idx_study_materials_content_hash already present")

        # 2b. guard duplicate active attempts before unique index
        if "idx_one_active_generated_attempt" not in _indexes(conn, "generated_quiz_attempts"):
            dups = conn.execute(
                "SELECT quiz_id, user_id, COUNT(*) AS n, GROUP_CONCAT(id) AS ids "
                "FROM generated_quiz_attempts WHERE submitted_at IS NULL "
                "GROUP BY quiz_id, user_id HAVING COUNT(*) > 1"
            ).fetchall()
            if dups:
                ok = False
                print("[blocked] duplicate active attempts prevent unique index:")
                for d in dups:
                    print(f"   quiz_id={d['quiz_id']} user_id={d['user_id']} "
                          f"count={d['n']} attempt_ids={d['ids']}")
            else:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_generated_attempt "
                    "ON generated_quiz_attempts(quiz_id, user_id) WHERE submitted_at IS NULL"
                )
                conn.commit()
                print("[ok] created idx_one_active_generated_attempt")
        else:
            print("[skip] idx_one_active_generated_attempt already present")

        return 0 if ok else 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(migrate())
