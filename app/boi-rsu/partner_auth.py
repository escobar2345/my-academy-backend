# -*- coding: utf-8 -*-
"""
BOI RSU - Partner Authentication Server (port 5056)
===================================================
Authenticates the two partner types and returns the dashboard data each is
allowed to see.

  * PARENT partners -> log in with the child's STUDENT TRACKING NUMBER
                       (e.g. STU0001). They see ONLY that student's cohort
                       activity (attendance, quizzes, assignments, lessons).
  * REAL partners   -> log in with the email + password the admin generated.
                       They see the full sponsor dashboard (sponsored
                       students + teacher-management data).

Reads the SAME PostgreSQL tables as the rest of the app and shares the exact
PBKDF2-SHA256 password scheme (120k iterations, 16-byte salt, hex) so the
admin-generated partner logins verify here without change.

Run:
    cd backend/app/boi-rsu
    python partner_auth.py
"""

import os
import sys
import hashlib
from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def _load_env_file():
    """Load backend/.env (and .env.local) into os.environ at import time.

    Mirrors pgdb.py so DATABASE_URL is picked up even when this server runs
    directly (not through the main app).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env.local"),
        os.path.join(here, ".env"),
        os.path.abspath(os.path.join(here, "..", "..", ".env")),
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
        except Exception:
            continue
        break


_load_env_file()

from pgdb import pg as _pg  # noqa: E402  (PostgreSQL chain-style client)


def _sb(resource, params=None):
    """Small PostgreSQL helper — same signature the old Supabase REST helper
    had, so every call site below keeps working unchanged.

    Params map (PostgREST style):
        {"student_id": "eq.STU0001", "select": "a,b,c",
         "order": "taken_on.desc", "limit": "10"}
    """
    params = params or {}
    query = _pg.table(resource)
    columns = params.pop("select", "*")
    query.select(columns)
    for key, value in list(params.items()):
        if value.startswith("eq."):
            query.eq(key, value[len("eq."):])
    order = params.pop("order", None)
    if order:
        col, _, direction = order.partition(".")
        query.order(col, ascending=(direction != "desc"))
    limit = params.pop("limit", None)
    if limit:
        query.limit(int(limit))
    return query.execute().data or []


def _pbkdf2(password, salt_hex, iterations=120_000):
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
        dklen=32,
    )
    return dk.hex()


def _verify_password(password, salt_hex, expected_hash):
    if not salt_hex or not expected_hash:
        return False
    try:
        return _pbkdf2(password, salt_hex) == expected_hash
    except Exception:
        return False
def _load_student(tracking_number):
    """Fetch one student by its tracking number (student_id)."""
    tracking_number = (tracking_number or "").strip().upper()
    if not tracking_number:
        return None
    rows = _sb(
        "students",
        {
            "student_id": f"eq.{tracking_number}",
            "select": "student_id,name,course_name,career_path,payment_status,sponsor_id,current_month,current_topic_index,overall_grade,avg_quiz_score",
        },
    )
    return rows[0] if rows else None


def _load_student_activity(student_id):
    """The cohort + activity for ONE student (parent view)."""
    qz = _sb("quiz_records", {"student_id": f"eq.{student_id}", "select": "topic,percentage,taken_on", "order": "taken_on.desc", "limit": "10"})
    at = _sb("attendance_records", {"student_id": f"eq.{student_id}", "select": "attended,recorded_on", "order": "recorded_on.desc", "limit": "10"})
    asm = _sb("assignment_records", {"student_id": f"eq.{student_id}", "select": "title,score,submitted_on", "order": "submitted_on.desc", "limit": "10"})
    return {
        "quizzes": qz,
        "attendance": at,
        "assignments": asm,
    }


def _load_partner_students(sponsor_id):
    return _sb("students", {"sponsor_id": f"eq.{sponsor_id}", "select": "student_id,name,course_name,career_path,payment_status,current_month,overall_grade,avg_quiz_score"})


def _load_partner_teacher_data():
    return _sb("teachers", {"status": "eq.active", "select": "teacher_id,name,login_email,specialty,status"})


app = Flask(__name__)
CORS(app)
app.json.ensure_ascii = False


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "partner-auth", "port": 5056})
# ---------------------------------------------------------------------------
# 1) PARENT login by student tracking number
# ---------------------------------------------------------------------------
@app.post("/api/auth/parent")
def auth_parent():
    body = request.get_json(silent=True) or {}
    tracking = (body.get("tracking_number") or body.get("tracking") or "").strip().upper()
    if not tracking:
        return jsonify({"success": False, "error": "Enter the student tracking number (e.g. STU0001)."}), 400
    try:
        student = _load_student(tracking)
        if not student:
            return jsonify({"success": False, "error": f"No student found with tracking number {tracking}. Double-check it with the school."}), 404
        activity = _load_student_activity(student["student_id"])
        return jsonify({
            "success": True,
            "auth_type": "parent",
            "session": {"type": "parent", "student_id": student["student_id"]},
            "student": student,
            "activity": activity,
        })
    except RuntimeError as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


# ---------------------------------------------------------------------------
# 2) REAL partner login by email + admin-generated password
# ---------------------------------------------------------------------------
@app.post("/api/auth/partner")
def auth_partner():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400
    try:
        rows = _sb("partners", {"login_email": f"eq.{email}", "select": "partner_id,org_name,contact_person,email,login_email,sponsor_id,status,partner_type,password_salt,password_hash"})
        if not rows:
            return jsonify({"success": False, "error": "No partner account with that email."}), 404
        rec = rows[0]
        if rec.get("status") != "active":
            return jsonify({"success": False, "error": "This partner account has been deactivated."}), 403
        if not _verify_password(password, rec.get("password_salt"), rec.get("password_hash")):
            return jsonify({"success": False, "error": "Wrong email or password."}), 401
        sponsor_id = rec["sponsor_id"]
        students = _load_partner_students(sponsor_id)
        teachers = _load_partner_teacher_data() if rec.get("partner_type", "partner") != "parent" else []
        return jsonify({
            "success": True,
            "auth_type": "partner",
            "session": {"type": "partner", "partner_id": rec["partner_id"]},
            "partner": {
                "partner_id": rec["partner_id"],
                "org_name": rec["org_name"],
                "contact_person": rec["contact_person"],
                "email": rec["email"],
                "login_email": rec["login_email"],
                "sponsor_id": sponsor_id,
                "partner_type": rec.get("partner_type", "partner"),
            },
            "students": students,
            "teachers": teachers,
            "activity": [],
        })
    except RuntimeError as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500


if __name__ == "__main__":
    print("Partner auth server on http://localhost:5056")
    app.run(host="0.0.0.0", port=5056, debug=False)