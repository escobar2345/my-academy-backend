# -*- coding: utf-8 -*-
"""
One-time migration: move students stuck in the local JSON fallback store
(C:\\Users\\Admin\\.openclaw-boirsu\\workspace\\students\\students.json)
into the PostgreSQL `students` table (DATABASE_URL, via pgdb).

Run with the backend venv python:
    cd backend
    .venv\\Scripts\\python.exe migrate_json_students.py

Safe to re-run: existing student_ids are upserted, not duplicated.
"""
import os
import sys
import json
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
BOI_RSU = os.path.join(BASE, "app", "boi-rsu")
sys.path.insert(0, BOI_RSU)

import pgdb  # noqa: E402  (PostgreSQL chain-style client)

JSON_PATH = os.path.join(os.path.expanduser("~"), ".openclaw-boirsu", "workspace", "students", "students.json")


def _jsonable(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    return v


def main():
    try:
        pgdb.initialise()
    except Exception as e:
        print(f"PostgreSQL not reachable via DATABASE_URL - cannot migrate. ({e})")
        return
    if not os.path.exists(JSON_PATH):
        print(f"No local JSON store found at {JSON_PATH} - nothing to migrate.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as fh:
        store = json.load(fh)

    # Real columns of the students table (from POSTGRES_SCHEMA.sql).
    # Unknown JSON keys (added by older code paths) are dropped here instead
    # of breaking the insert with an unknown-column error.
    from pgdb import _run  # noqa: E402
    rows = _run(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'students'"
    )
    student_cols = {r["column_name"] for r in (rows or [])}

    print(f"Migrating {len(store)} student(s) from JSON -> PostgreSQL...")
    ok = fail = 0
    for student_id, student in store.items():
        if not isinstance(student, dict):
            continue
        payload = {k: _jsonable(v) for k, v in student.items() if k in student_cols}
        payload["student_id"] = student_id  # never lose the tracking number
        try:
            pgdb.pg.table("students").upsert(payload, onConflict="student_id").execute()
            ok += 1
            print(f"  OK    {student_id} -> {student.get('name', '?')}")
        except Exception as e:
            fail += 1
            print(f"  FAIL  {student_id}: {str(e)[:200]}")

    print(f"Done. migrated={ok} failed={fail}")
    if ok:
        print("NOTE: their passwords (salt+hash) came across too, so their")
        print("student logins keep working from the PostgreSQL record.")


if __name__ == "__main__":
    main()
