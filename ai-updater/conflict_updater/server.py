"""Local control panel — a FastAPI server that wraps the pipeline behind a browser dashboard.

Launch with `python -m conflict_updater serve`, open the printed URL, and drive everything from
the page: watch the coverage (honesty) map, run scans, review what's waiting, approve into the
seed. It's a LOCAL admin tool by nature (it holds your keys and writes seed.json), so it binds to
localhost by default and is never deployed.
"""
import dataclasses
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .config import load_settings
from .llm import get_llm
from .search import get_search
from .store import (
    load_base, write_result, load_seed_dict, write_seed_dict, load_proposals,
    append_coverage, load_coverage, accept_reviewed,
)
from .schema import ScanRequest
from .pipeline import scan
from . import merge

_HERE = Path(__file__).resolve().parent


# ---------------- background jobs ----------------

class Job:
    def __init__(self, label: str):
        self.id = uuid.uuid4().hex[:8]
        self.label = label
        self.status = "running"          # running | done | error
        self.detail = ""
        self.started = datetime.now().strftime("%H:%M:%S")

    def as_dict(self):
        return {"id": self.id, "label": self.label, "status": self.status,
                "detail": self.detail, "started": self.started}


_jobs: list[Job] = []
_jobs_lock = threading.Lock()
_scan_lock = threading.Lock()   # serialize scans (one at a time — rate limits, shared stdout)


def _run_scan(job: Job, period_start: str, period_end: str, region, limit: int):
    with _scan_lock:
        try:
            settings = load_settings()
            if limit:
                settings = dataclasses.replace(settings, max_candidates=limit)
            req = ScanRequest(period_start=period_start, period_end=period_end, region=region or None)
            base = load_base(settings.seed_json)
            result = scan(req, llm=get_llm(settings), search=get_search(settings),
                          base=base, settings=settings)
            write_result(result, settings.output_dir)
            append_coverage(settings.output_dir / "coverage.json", result, limited=settings.max_candidates)
            s = result.stats
            job.detail = (f"{s.get('proposals', 0)} proposals "
                          f"({s.get('needs_human', 0)} to review), {s.get('dropped', 0)} already-known")
            job.status = "done"
        except Exception as e:  # noqa: BLE001
            job.status = "error"
            job.detail = f"{type(e).__name__}: {e}"[:400]


def start_scan(period_start: str, period_end: str, region, limit: int) -> Job:
    label = f"scan {period_start}..{period_end}" + (f" · {region}" if region else "")
    job = Job(label)
    with _jobs_lock:
        _jobs.insert(0, job)
        del _jobs[20:]
    threading.Thread(target=_run_scan, args=(job, period_start, period_end, region, limit),
                     daemon=True).start()
    return job


# ---------------- reading pipeline state ----------------

def _item(p: dict) -> dict:
    e = p["event"]
    ver = p.get("verify") or {}
    return {
        "date": e.get("date"), "title": e.get("title"), "kind": e.get("kind"),
        "severity": e.get("severity"),
        "target": p.get("target_conflict_id"), "is_new": bool(p.get("new_conflict")),
        "location": (e.get("location") or {}).get("label"),
        "sources": len(e.get("sources", [])),
        "confidence": ver.get("confidence"),
        "question": ver.get("open_question"),
        "provisional": p.get("provisional", False),
    }


def _pending(out_dir: Path) -> list[dict]:
    out = []
    for f in sorted(out_dir.glob("proposals_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        props = data.get("proposals", [])
        req = data.get("request", {})
        human, auto = [], []
        for p in props:
            (human if p.get("needs_human") else auto).append(_item(p))
        for n, it in enumerate(human, 1):
            it["n"] = n
        if not (human or auto):
            continue
        out.append({
            "file": f.name,
            "period": f"{req.get('period_start')}..{req.get('period_end')}",
            "region": req.get("region") or "—",
            "human": human, "auto": auto,
            "dropped": data.get("dropped", []),
        })
    return out


def _recent(out_dir: Path) -> list[dict]:
    log = out_dir / "applied_log.json"
    if not log.exists():
        return []
    try:
        return list(reversed(json.loads(log.read_text(encoding="utf-8"))))[:20]
    except Exception:
        return []


def data_list() -> list[dict]:
    """The atlas contents as a flat list (for browsing in the panel — not the map)."""
    settings = load_settings()
    try:
        d = json.loads(Path(settings.seed_json).read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for c in d.get("conflicts", []):
        out.append({
            "id": c["id"], "title": c.get("title"), "type": c.get("type"),
            "severity": c.get("severity"), "start": c.get("startDate"), "end": c.get("endDate"),
            "status": c.get("status"), "ongoing": c.get("ongoing"),
            "countries": c.get("involvedCountries", []), "events": len(c.get("events", [])),
        })
    return out


def _seed_stats(seed_path: Path) -> dict:
    try:
        d = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    except Exception:
        return {"version": "?", "conflicts": 0, "events": 0}
    return {
        "version": d.get("version"),
        "conflicts": len(d.get("conflicts", [])),
        "events": sum(len(c.get("events", [])) for c in d.get("conflicts", [])),
    }


def overview() -> dict:
    settings = load_settings()
    out_dir = settings.output_dir
    with _jobs_lock:
        jobs = [j.as_dict() for j in _jobs]
    return {
        "seed": _seed_stats(settings.seed_json),
        "provider": {"llm": f"{settings.llm_provider}:{settings.llm_model}",
                     "search": settings.search_backend},
        "coverage": load_coverage(out_dir / "coverage.json"),
        "pending": _pending(out_dir),
        "recent": _recent(out_dir),
        "jobs": jobs,
        "running": any(j["status"] == "running" for j in jobs),
    }


def apply_file(file_name: str, approve=None, approve_all: bool = False) -> dict:
    settings = load_settings()
    out_dir = settings.output_dir
    path = out_dir / Path(file_name).name          # never escape out_dir
    if not path.exists():
        return {"ok": False, "error": f"no such proposals file: {file_name}"}
    proposals = load_proposals(path)
    accept_reviewed(proposals, approve, approve_all)

    seed = load_seed_dict(settings.seed_json)
    before = set(merge.validate(seed))
    landed = [p for p in proposals if not p.needs_human and not p.provisional]
    seed, report = merge.apply(proposals, seed)
    new_issues = sorted(set(merge.validate(seed)) - before)
    if new_issues:
        return {"ok": False, "error": "would introduce incoherence", "issues": new_issues, "report": report}

    write_seed_dict(settings.seed_json, seed)
    _log_applied(out_dir, path.name, [p.event.title for p in landed])
    _rewrite_or_remove(path, proposals)
    return {"ok": True, "applied": len(landed), "report": report,
            "titles": [p.event.title for p in landed]}


def _log_applied(out_dir: Path, file_name: str, titles: list[str]):
    log = out_dir / "applied_log.json"
    data = []
    if log.exists():
        try:
            data = json.loads(log.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append({"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "file": file_name, "titles": titles})
    log.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _rewrite_or_remove(path: Path, proposals):
    """Keep only the proposals that did NOT land (still need review / provisional), so the review
    queue shrinks to exactly what's left. Remove the file when nothing is left."""
    remaining = [p for p in proposals if p.needs_human or p.provisional]
    if not remaining:
        path.unlink(missing_ok=True)
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    kept_titles = {(p.event.date, p.event.title) for p in remaining}
    data["proposals"] = [p for p in data.get("proposals", [])
                         if (p["event"]["date"], p["event"]["title"]) in kept_titles]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- the web app ----------------

def create_app():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    app = FastAPI(title="Conflict Atlas — Pipeline Control")

    class ScanBody(BaseModel):
        period_start: str
        period_end: str
        region: str | None = None
        limit: int = 0

    class ApplyBody(BaseModel):
        file: str
        approve: list[int] = []
        approve_all: bool = False

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (_HERE / "dashboard.html").read_text(encoding="utf-8")

    @app.get("/api/overview")
    def api_overview():
        return JSONResponse(overview())

    @app.get("/api/data")
    def api_data():
        return JSONResponse(data_list())

    @app.post("/api/scan")
    def api_scan(body: ScanBody):
        job = start_scan(body.period_start, body.period_end, body.region, body.limit)
        return {"ok": True, "job": job.as_dict()}

    @app.post("/api/apply")
    def api_apply(body: ApplyBody):
        return JSONResponse(apply_file(body.file, body.approve, body.approve_all))

    return app


def serve(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    print("\n  Conflict Atlas — Pipeline Control")
    print(f"  open  ->  http://{host}:{port}\n")
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
