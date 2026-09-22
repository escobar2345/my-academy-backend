# -*- coding: utf-8 -*-
"""
pgdb.py — PostgreSQL database layer (replaces Supabase)
=======================================================
Connection pool + auto schema initialisation + a small chain-style
query client that mirrors the shape of the old supabase-py calls:

    from pgdb import pg

    rows = pg.table("students").select("*").eq("payment_status", "paid").execute().data
    pg.table("students").insert(row).execute()
    pg.table("students").update(payload).eq("student_id", sid).execute()
    one  = pg.table("students").select("*").eq("email", e).maybeSingle().execute().data
    n    = pg.table("students").select("*", count="exact").eq("status", "active").execute().count

Every `.execute()` returns `.data` (list[dict] | dict | None) and `.count`
(int | None), matching what boirsu.py / partner_auth.py / api_server.py
already destructure.

Config: reads DATABASE_URL from backend/.env (or the real environment),
defaulting to postgres://postgres:postgres@localhost:5432/mirofish.
The DDL in backend/POSTGRES_SCHEMA.sql is applied automatically on first
connect (idempotent CREATE TABLE IF NOT EXISTS everywhere).
"""

import os
import json
import datetime
import decimal
import uuid
import threading

try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
except ImportError:  # pragma: no cover
    psycopg2 = None


def _mask(url: str) -> str:
    """DATABASE_URL with the password hidden — safe for logs/prints."""
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        netloc = parts.netloc
        cred, _, hostport = parts.netloc.rpartition("@")
        if cred and ":" in cred:
            netloc = cred.split(":", 1)[0] + ":***@" + hostport
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def _load_env_file():
    """Load backend/.env (and .env.local) into os.environ at import time."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env.local"),
        os.path.join(here, ".env"),
        os.path.abspath(os.path.join(here, "..", "..", ".env")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "backend", ".env")),
        os.path.join(os.getcwd(), ".env.local"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception as e:
            print(f"[WARN] pgdb: could not parse env file {path}: {e}")
        break


_load_env_file()

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or "postgresql://postgres:postgres@localhost:5432/mirofish"
)

# Pool sizing — tune for production via backend/.env, e.g.:
#   DB_POOL_MIN=2
#   DB_POOL_MAX=10
#   DB_STATEMENT_TIMEOUT_MS=15000   # kill queries stuck > 15s
# With multiple server processes, total connections = MAX x processes.
# Beyond ~40-50 total connections, put PgBouncer in front of PostgreSQL.
DB_POOL_MIN = max(1, int(os.environ.get("DB_POOL_MIN", "2")))
DB_POOL_MAX = max(DB_POOL_MIN, int(os.environ.get("DB_POOL_MAX", "8")))
DB_STATEMENT_TIMEOUT_MS = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "15000"))

_pool = None
_pool_lock = threading.Lock()
_init_done = threading.Event()
_jsonb_cols = {}          # table -> set[columns] that are JSONB (write adaptation)
INIT_ERROR = None


def _get_pool():
    global _pool, INIT_ERROR
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed. Install with: pip install psycopg2-binary"
        )
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=DB_POOL_MIN, maxconn=DB_POOL_MAX, dsn=DATABASE_URL,
                        options=f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}",
                    )
                except Exception as e:
                    INIT_ERROR = e
                    raise
                print(f"[OK] PostgreSQL pool created: {_mask(DATABASE_URL)}")
    return _pool


def _schema_path():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..", "POSTGRES_SCHEMA.sql")),
        os.path.join(os.getcwd(), "POSTGRES_SCHEMA.sql"),
        os.path.join(here, "POSTGRES_SCHEMA.sql"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _apply_schema(cur):
    """Apply POSTGRES_SCHEMA.sql (idempotent CREATE ... IF NOT EXISTS DDL)."""
    path = _schema_path()
    if not path:
        print("[WARN] pgdb: POSTGRES_SCHEMA.sql not found — skipping schema init")
        return
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    except Exception:
        # Extension creation needs superuser; gen_random_uuid() is built in
        # on PostgreSQL 13+ anyway.
        pass
    cur.execute(sql)
    print(f"[OK] PostgreSQL schema applied from {path}")


def _cache_jsonb_columns(cur):
    cur.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type = 'jsonb'"
    )
    for table, column in cur.fetchall():
        _jsonb_cols.setdefault(table, set()).add(column)


def initialise(force=False):
    """Connect + apply the schema exactly once (thread-safe)."""
    if _init_done.is_set() and not force:
        return
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            _apply_schema(cur)
            _cache_jsonb_columns(cur)
        conn.commit()
        _init_done.set()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Value adaptation (Postgres rows -> JSON-friendly dicts, like the old API)
# ---------------------------------------------------------------------------
def _adapt_value(v):
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def _adapt_row(row):
    return {k: _adapt_value(v) for k, v in row.items()} if row else row


class PgError(Exception):
    """DB error carrying the Postgres error code (23505 duplicate key,
    42P01 missing table, ...) in `.code` — the portal pages translate
    these into friendly messages."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code or ""


def _serialize(table, payload):
    """JSON-encode lists/dicts written to JSONB columns (goals,
    preferred_daily_times, sections, courses, facilities, ...)."""
    cols = _jsonb_cols.get(table, set())
    out = {}
    for k, v in (payload or {}).items():
        if k in cols and not isinstance(v, (str, int, float, bool, type(None))):
            out[k] = json.dumps(v)
        else:
            out[k] = v
    return out


def _run(query_sql, params=None, fetch="all"):
    """Execute one statement on a pooled connection; commit writes."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query_sql, params or ())
            data = None
            if fetch == "all":
                data = [_adapt_row(r) for r in cur.fetchall()]
            elif fetch == "one":
                row = cur.fetchone()
                data = _adapt_row(row) if row else None
            conn.commit()
        return data
    except Exception as e:
        conn.rollback()
        code = getattr(e, "pgcode", "") or ""
        msg = str(e)
        if code == "23505":
            msg = f"duplicate key value violates unique constraint ({msg})"
        elif code == "42P01" or ("relation" in msg and "does not exist" in msg):
            msg = f"Could not find the table in the database: {msg}"
            code = code or "PGRST205"
        raise PgError(msg, code)
    finally:
        pool.putconn(conn)


class PgQuery:
    """Chain-style builder: .select() / .eq() / .limit() / .order() /
    .single() / .insert() / .upsert() / .update() ... .execute().
    Mirrors the old supabase-py call pattern 1:1."""

    def __init__(self, client, table):
        self._client = client
        self._table = table
        self._columns = "*"
        self._wheres = []
        self._ins = []            # (column, values) -> WHERE col IN (...)
        self._limit = None
        self._order = None
        self._single = False
        self._want_count = False
        self._action = "select"
        self._row = None
        self._conflict = None

    # -- chain builders ------------------------------------------------------
    def select(self, columns="*", count=None):
        self._columns = columns or "*"
        if count:
            self._want_count = True
        return self

    def eq(self, column, value):
        self._wheres.append((column, value))
        return self

    def in_(self, column, values):
        """WHERE column IN (values) — used by the partner dashboard to
        scope activity records to one sponsor's students."""
        if values is not None:
            self._ins.append((column, list(values)))
        return self

    def limit(self, n):
        self._limit = int(n)
        return self

    def order(self, column, ascending=True):
        self._order = (column, ascending)
        return self

    def single(self):
        self._single = True
        return self

    def maybeSingle(self):
        self._single = True
        return self

    def insert(self, row, onConflict=None):
        self._action = "upsert" if onConflict else "insert"
        self._row = row
        self._conflict = onConflict
        return self

    def upsert(self, row, onConflict=None):
        self._action = "upsert"
        self._row = row
        self._conflict = onConflict
        return self

    def update(self, row):
        self._action = "update"
        self._row = row
        return self

    # -- execution -------------------------------------------------------------
    def execute(self):
        initialise()
        if self._action == "select":
            return self._execute_select()
        return self._execute_write()

    def _execute_select(self):
        table = self._client.q(self._table)
        where_sql, params = self._client._build_where(self._wheres, self._ins)
        if self._want_count:
            sql = f"SELECT COUNT(*)::int AS n FROM {table}{where_sql}"
            rows = _run(sql, params)
            return Result([], rows[0]["n"] if rows else 0)
        sql = f"SELECT {self._columns} FROM {table}{where_sql}"
        if self._order:
            col, asc = self._order
            sql += f" ORDER BY {self._client.q(col)} {'ASC' if asc else 'DESC'}"
        if self._limit is not None:
            sql += f" LIMIT {int(self._limit)}"
        if self._single:
            data = _run(sql, params, fetch="one")
            return Result(data)
        data = _run(sql, params, fetch="all")
        return Result(data)

    def _execute_write(self):
        table = self._client.q(self._table)
        if self._action == "update":
            return self._execute_update(table)
        rows = self._row if isinstance(self._row, list) else [self._row]
        rows = [_serialize(self._table, r) for r in rows if r]
        if not rows:
            return Result([])
        cols = list(rows[0].keys())
        col_sql = ", ".join(self._client.q(c) for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = f"INSERT INTO {table} ({col_sql}) VALUES "
        values = []
        row_sql = []
        for r in rows:
            row_sql.append(f"({placeholders})")
            values.extend(r.get(c) for c in cols)
        sql += ", ".join(row_sql)
        if self._action == "upsert" and self._conflict:
            conflict_cols = [c.strip() for c in str(self._conflict).split(",") if c.strip()]
            conflict_sql = ", ".join(self._client.q(c) for c in conflict_cols)
            updates = [
                f"{self._client.q(c)} = EXCLUDED.{self._client.q(c)}"
                for c in cols if c not in conflict_cols
            ]
            if updates:
                sql += f" ON CONFLICT ({conflict_sql}) DO UPDATE SET {', '.join(updates)}"
            else:
                # Row carries only the conflict key — nothing to update.
                sql += f" ON CONFLICT ({conflict_sql}) DO NOTHING"
        sql += " RETURNING *"
        data = _run(sql, values)
        if self._single:
            return Result(data[0] if data else None)
        return Result(data)

    def _execute_update(self, table):
        """UPDATE <table> SET <realfields> WHERE <eq...>  RETURNING *"""
        payload = _serialize(self._table, self._row or {})
        if not payload:
            return Result([])
        set_clauses = []
        values = []
        for k, v in payload.items():
            set_clauses.append(f"{self._client.q(k)} = %s")
            values.append(v)
        if not self._wheres and not self._ins:
            raise PgError("update() requires at least one .eq(column, value) filter")
        where_sql, where_params = self._client._build_where(self._wheres, self._ins)
        sql = (
            f"UPDATE {table} SET {', '.join(set_clauses)}{where_sql} RETURNING *"
        )
        data = _run(sql, values + where_params)
        if self._single:
            return Result(data[0] if data else None)
        return Result(data)


class Result:
    """`.execute()` return value: `.data` + optional `.count`."""

    __slots__ = ("data", "count")

    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class PgClient:
    """Entry point: `pg.table(name)` returns a chain-style query builder."""

    def __init__(self):
        self.pg_version = None

    @staticmethod
    def q(identifier):
        """Quote an SQL identifier (column / table name)."""
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _build_where(wheres, ins=None):
        if not wheres and not ins:
            return "", []
        clauses = []
        params = []
        for column, value in (wheres or []):
            clauses.append(f"{PgClient.q(column)} = %s")
            params.append(value)
        for column, values in (ins or []):
            if not values:
                # IN () with no values can never match — short-circuit.
                return " WHERE 1 = 0", []
            placeholders = ", ".join(["%s"] * len(values))
            clauses.append(f"{PgClient.q(column)} IN ({placeholders})")
            params.extend(values)
        return " WHERE " + " AND ".join(clauses), params

    def table(self, name):
        return PgQuery(self, name)

    def health(self):
        initialise()
        rows = _run("SELECT version() AS v", fetch="one")
        self.pg_version = rows.get("v") if rows else None
        return {"ok": True, "url": _mask(DATABASE_URL), "version": self.pg_version}


# Shared client instances — imported everywhere.
pg = PgClient()
# Compatibility alias for code that used to call `supabase.table(...)`.
db = pg


if __name__ == "__main__":
    # Self-test:  python pgdb.py
    try:
        print(json.dumps(pg.health(), indent=2))
        probe = pg.table("students").select("*", count="exact").limit(1).execute()
        print(f"students table reachable (count={probe.count})")
        fees = pg.table("course_fees").select("course,amount").limit(3).execute()
        print(f"course_fees sample: {fees.data}")
        print("[OK] pgdb self-test passed")
    except Exception as e:
        code = getattr(e, "code", "")
        print(f"[!] pgdb self-test failed{f' (code {code})' if code else ''}: {e}")
        raise SystemExit(1)



