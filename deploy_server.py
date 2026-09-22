"""
BOI RSU - Production deployment server (Railway / Docker).

Local development runs three Flask processes on ports 5001 (run.py),
5055 (api_server.py) and 5056 (partner_auth.py) with the Vite dev proxy
in front (see frontend/vite.config.js). Production has no Vite dev
server, so this single entrypoint recreates that exact routing inside
ONE process on ONE port ($PORT):

    /api/auth/*      -> partner_auth.py  (parent + partner login)
    /api/{ai,stream,students,student,attendance,assignment,careers,
          roadmap,progress,paystack,textbooks,classroom,timetable,
          start-ai-class,videos}
                     -> api_server.py    (classroom, AI, payments, textbooks)
    /api/* , /health -> main boirsu app  (run.py create_app)
    everything else  -> the built frontend (frontend/dist) with an
                        index.html fallback (vue-router history mode)

Every backend app defines absolute routes (e.g. "/api/classroom/state"),
so requests are forwarded with PATH_INFO unchanged - exactly like the dev
proxy. One service, one URL, zero CORS, zero hardcoded hosts.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
BOI_RSU_DIR = os.path.join(BASE, "app", "boi-rsu")
FRONTEND_DIST = os.path.abspath(os.path.join(BASE, "..", "frontend", "dist"))

# sys.path order matters: "app" must resolve to the backend/app PACKAGE
# (like run.py does), not to app/boi-rsu/app.py (an unrelated legacy file).
# Inserting BOI_RSU_DIR first and then BASE at position 0 guarantees
# BASE wins while boi-rsu stays importable for api_server/partner_auth.
sys.path.insert(0, BOI_RSU_DIR)
sys.path.insert(0, BASE)
for _p in (BASE, BOI_RSU_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, jsonify, send_from_directory  # noqa: E402
from werkzeug.serving import run_simple  # noqa: E402

from app import create_app  # noqa: E402  (main boirsu app - same as run.py)
import api_server as boi_api_server  # noqa: E402  (classroom / AI / payments)
import partner_auth as boi_partner_auth  # noqa: E402  (partner + parent auth)

main_app = create_app()
api_app = boi_api_server.app
auth_app = boi_partner_auth.app

# Prefixes owned by api_server.py - keep in sync with frontend/vite.config.js
# (order does not matter here; longest/most-specific prefixes are listed first
# only for readability. "/api/student" and "/api/students" are both exact
# prefixes and never shadow each other thanks to the "/"-aware matcher below).
API_SERVER_PREFIXES = (
    "/api/ai",
    "/api/stream",
    "/api/students",
    "/api/student",
    "/api/attendance",
    "/api/assignment",
    "/api/careers",
    "/api/roadmap",
    "/api/progress",
    "/api/paystack",
    "/api/textbooks",
    "/api/classroom",
    "/api/timetable",
    "/api/start-ai-class",
    "/api/videos",
)

# ---- Static frontend (built by `npm run build` into frontend/dist) ----
static_app = Flask(__name__, static_folder=None)


@static_app.get("/healthz")
def healthz():
    return jsonify(
        {
            "ok": True,
            "service": "boi-rsu-production",
            "mounted": ["main", "api_server", "partner_auth"],
        }
    )


@static_app.route("/", defaults={"path": ""})
@static_app.route("/<path:path>")
def spa(path):
    candidate = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(candidate):
        return send_from_directory(FRONTEND_DIST, path)
    # SPA fallback: vue-router uses history mode, so client-side URLs like
    # /admin or /classroom/teacher must serve index.html.
    return send_from_directory(FRONTEND_DIST, "index.html")


class PrefixDispatcher:
    """Minimal WSGI router - forwards PATH_INFO unchanged, like the dev proxy."""

    def __init__(self, mounts, fallback):
        self.mounts = mounts
        self.fallback = fallback

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        for prefix, target in self.mounts:
            if path == prefix or path.startswith(prefix + "/"):
                return target(environ, start_response)
        return self.fallback(environ, start_response)


dispatcher = PrefixDispatcher(
    mounts=[("/api/auth", auth_app)]
    + [(prefix, api_app) for prefix in API_SERVER_PREFIXES]
    + [("/api", main_app), ("/health", main_app)],
    fallback=static_app,
)

if __name__ == "__main__":
    # Make sure the uploads folder exists (teacher PDFs / generated lessons).
    os.makedirs(os.path.join(BASE, "uploads"), exist_ok=True)
    port = int(os.environ.get("PORT", "8000"))
    print(f"[deploy] serving frontend + 3 backends on 0.0.0.0:{port}", flush=True)
    run_simple("0.0.0.0", port, dispatcher, threaded=True)
