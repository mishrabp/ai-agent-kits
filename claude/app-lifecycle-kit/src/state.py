# Lifecycle state engine: the single source of truth for requirements, design, code, tests and deployments.
# State lives in <project>/.lifecycle/state.json (commit it). Markdown views are re-rendered on every save.
import json
import os
import re
from datetime import datetime, timezone

from render import render_all

DIR = ".lifecycle"
SCHEMA = 1
DESIGN_SECTIONS = [
    "overview", "architecture", "components", "data_model", "api", "ui",
    "security", "non_functional", "deployment", "testing_strategy",
]
REQ_STATUS = ["draft", "approved", "retired"]
PRIORITY = ["must", "should", "could"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def compact(d):
    """Drops None values, so optional fields are left out of state.json rather than written as null."""
    return {k: v for k, v in d.items() if v is not None}


def project_dir():
    v = os.environ.get("LIFECYCLE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    # An unresolved plugin variable can arrive as literal "${...}" text.
    return v if v and not v.startswith("${") else os.getcwd()


def state_path(root):
    return os.path.join(root, DIR, "state.json")


def has_state(root):
    return os.path.exists(state_path(root))


def load(root):
    if not has_state(root):
        return None
    with open(state_path(root), encoding="utf-8") as f:
        s = json.load(f)
    if s.get("schema") != SCHEMA:
        raise ValueError(f"Unsupported state schema {s.get('schema')} (expected {SCHEMA})")
    return s


def save(root, s):
    s["project"]["updated_at"] = now()
    d = os.path.join(root, DIR)
    os.makedirs(d, exist_ok=True)
    tmp = f"{state_path(root)}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, state_path(root))  # atomic: the hook and the MCP server may both write
    render_all(d, s, analyze(s))


def mutate(root, fn):
    """Load, apply fn, save. Raises if the project has not been initialised."""
    s = load(root)
    if not s:
        raise ValueError(f"No lifecycle project in {root}. Call init_project first.")
    result = fn(s)
    save(root, s)
    return result


def next_id(items, prefix):
    def num(x):
        try:
            return int(x["id"].split("-")[1])
        except (IndexError, ValueError):
            return 0

    n = max([num(x) for x in items], default=0) + 1
    return f"{prefix}-{n:03d}"


def log(s, event, detail):
    s["log"].append(compact({"at": now(), "event": event, "detail": detail, "change_id": s.get("current_change") or None}))
    if len(s["log"]) > 300:
        del s["log"][: len(s["log"]) - 300]


def req_by_id(s, rid):
    return next((r for r in s["requirements"] if r["id"] == rid), None)


def assert_reqs(s, ids=()):
    missing = [i for i in ids if not req_by_id(s, i)]
    if missing:
        raise ValueError(f"Unknown requirement id(s): {', '.join(missing)}")


def one_of(value, allowed, field):
    if value is not None and value not in allowed:
        raise ValueError(f'{field} must be one of {", ".join(allowed)} (got "{value}")')


def norm_file(root, f):
    rel = os.path.relpath(f, root) if os.path.isabs(f) else f
    rel = rel.replace(os.sep, "/")
    return rel[2:] if rel.startswith("./") else rel


# ---------------------------------------------------------------- operations


def init_project(root, name, summary="", kind="app", stack=""):
    if has_state(root):
        raise ValueError(f"A lifecycle project already exists in {root}. Use status to see it.")
    t = now()
    s = {
        "schema": SCHEMA,
        "project": {"name": name, "summary": summary, "kind": kind, "stack": stack, "created_at": t, "updated_at": t},
        "requirements": [],
        "design": {"sections": {}, "decisions": []},
        "code": {"links": {}, "changed_files": [], "last_change_at": None},
        "tests": {"runs": [], "criteria": {}},
        "deploy": {"target": None, "environments": {}, "history": []},
        "changes": [],
        "current_change": None,
        "log": [],
    }
    log(s, "init", f'Project "{name}" created')
    save(root, s)
    return s["project"]


def update_project(s, **fields):
    for k in ("name", "summary", "kind", "stack"):
        if fields.get(k) is not None:
            s["project"][k] = fields[k]
    log(s, "project", "Project details updated")
    return s["project"]


def upsert_requirement(s, id=None, title=None, description=None, kind=None, priority=None, status=None, acceptance_criteria=None):
    one_of(status, REQ_STATUS, "status")
    one_of(priority, PRIORITY, "priority")
    one_of(kind, ["functional", "non_functional"], "kind")

    def criteria(texts, req_id):
        return [{"id": f"{req_id}.AC{i + 1}", "text": text} for i, text in enumerate(texts)]

    if id:
        r = req_by_id(s, id)
        if not r:
            raise ValueError(f"Unknown requirement {id}")
        content_changed = False
        if title is not None and title != r["title"]:
            r["title"] = title
            content_changed = True
        if description is not None and description != r["description"]:
            r["description"] = description
            content_changed = True
        if acceptance_criteria:
            new = criteria(acceptance_criteria, r["id"])
            if new != r["acceptance_criteria"]:
                r["acceptance_criteria"] = new
                content_changed = True
        if kind:
            r["kind"] = kind
        if priority:
            r["priority"] = priority
        if status:
            r["status"] = status
        if content_changed:
            # A new revision makes linked design sections, tests and deployments stale (see analyze()).
            r["revision"] += 1
            if s.get("current_change") and s["current_change"] not in r["changes"]:
                r["changes"].append(s["current_change"])
        r["updated_at"] = now()
        log(s, "requirement", f"{r['id']} updated" + (f" (revision {r['revision']})" if content_changed else ""))
        return r

    if not title:
        raise ValueError("title is required for a new requirement")
    if not acceptance_criteria:
        raise ValueError("A new requirement needs at least one acceptance criterion")
    new_id = next_id(s["requirements"], "REQ")
    r = {
        "id": new_id,
        "title": title,
        "description": description or "",
        "kind": kind or "functional",
        "priority": priority or "must",
        "status": status or "draft",
        "acceptance_criteria": criteria(acceptance_criteria, new_id),
        "revision": 1,
        "changes": [s["current_change"]] if s.get("current_change") else [],
        "created_at": now(),
        "updated_at": now(),
    }
    s["requirements"].append(r)
    log(s, "requirement", f"{r['id']} added: {title}")
    return r


def set_design_section(s, section, content, requirement_ids=()):
    if not section or not re.fullmatch(r"[a-z0-9_]+", section):
        raise ValueError("section must be snake_case, e.g. data_model")
    requirement_ids = list(requirement_ids)
    assert_reqs(s, requirement_ids)
    prev = s["design"]["sections"].get(section)
    s["design"]["sections"][section] = {
        "content": content,
        "requirement_ids": requirement_ids,
        # Snapshot of the requirement revisions this section was written against.
        "req_revisions": {rid: req_by_id(s, rid)["revision"] for rid in requirement_ids},
        "revision": ((prev or {}).get("revision") or 0) + 1,
        "updated_at": now(),
    }
    log(s, "design", f'Section "{section}" {"updated" if prev else "added"}')
    return {"section": section, "revision": s["design"]["sections"][section]["revision"]}


def record_decision(s, title, decision, context="", alternatives="", consequences="", requirement_ids=(), supersedes=None):
    requirement_ids = list(requirement_ids)
    assert_reqs(s, requirement_ids)
    d = {
        "id": next_id(s["design"]["decisions"], "DEC"),
        "title": title, "context": context, "decision": decision, "alternatives": alternatives,
        "consequences": consequences, "requirement_ids": requirement_ids,
        "status": "accepted",
        "date": now()[:10],
    }
    if supersedes:
        old = next((x for x in s["design"]["decisions"] if x["id"] == supersedes), None)
        if not old:
            raise ValueError(f"Unknown decision {supersedes}")
        old["status"] = f"superseded by {d['id']}"
    s["design"]["decisions"].append(d)
    log(s, "decision", f"{d['id']}: {title}")
    return d


def link_code(root, s, requirement_ids, files):
    assert_reqs(s, requirement_ids)
    rel = [norm_file(root, f) for f in files]
    for rid in requirement_ids:
        s["code"]["links"][rid] = sorted(set(s["code"]["links"].get(rid, []) + rel))
    log(s, "code", f"Linked {len(rel)} file(s) to {', '.join(requirement_ids)}")
    return {rid: s["code"]["links"][rid] for rid in requirement_ids}


def unlink_code(root, s, requirement_id, files):
    assert_reqs(s, [requirement_id])
    drop = {norm_file(root, f) for f in files}
    s["code"]["links"][requirement_id] = [f for f in s["code"]["links"].get(requirement_id, []) if f not in drop]
    log(s, "code", f"Unlinked {len(drop)} file(s) from {requirement_id}")
    return s["code"]["links"][requirement_id]


def track_edit(root, file_path):
    """Called by the PostToolUse hook for every Edit/Write. Cheap and silent; no-op outside lifecycle projects."""
    if not file_path or not has_state(root):
        return False
    rel = norm_file(root, file_path)
    if rel.startswith(("..", f"{DIR}/")):
        return False
    s = load(root)
    changed = s["code"]["changed_files"]
    if rel not in changed:
        changed.append(rel)
    if len(changed) > 500:
        del changed[: len(changed) - 500]
    s["code"]["last_change_at"] = now()
    save(root, s)
    return True


def record_test_run(s, command, passed, failed, skipped=0, results=(), commit=None, notes=""):
    run_id = next_id(s["tests"]["runs"], "RUN")
    at = now()
    known = {c["id"]: r for r in s["requirements"] for c in r["acceptance_criteria"]}
    unknown = []
    for res in results:
        one_of(res["status"], ["pass", "fail", "skip"], f"status of {res['criterion_id']}")
        r = known.get(res["criterion_id"])
        if not r:
            unknown.append(res["criterion_id"])
            continue
        s["tests"]["criteria"][res["criterion_id"]] = {
            "test": res["test"], "status": res["status"], "run_id": run_id, "at": at, "req_revision": r["revision"],
        }
    run = compact({
        "id": run_id, "at": at, "command": command, "passed": passed, "failed": failed, "skipped": skipped,
        "commit": commit, "notes": notes, "criteria_reported": len(results) - len(unknown),
    })
    s["tests"]["runs"].append(run)
    if len(s["tests"]["runs"]) > 100:
        del s["tests"]["runs"][: len(s["tests"]["runs"]) - 100]
    # A fully green run means the current code has been verified.
    if failed == 0:
        s["code"]["changed_files"] = []
    log(s, "test", f"{run_id}: {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
    return {"run": run, "unknown_criteria": unknown}


def set_deploy_config(s, target=None, environments=()):
    if target:
        s["deploy"]["target"] = target
    for e in environments:
        if not e.get("name"):
            raise ValueError("Each environment needs a name")
        s["deploy"]["environments"][e["name"]] = {**s["deploy"]["environments"].get(e["name"], {}), **e}
    envs = ", ".join(s["deploy"]["environments"]) or "none"
    log(s, "deploy-config", f"Target {s['deploy']['target']}; environments: {envs}")
    return s["deploy"]


def record_deployment(s, environment, status, version=None, commit=None, url=None, notes=""):
    one_of(status, ["success", "failed", "rolled_back"], "status")
    if environment not in s["deploy"]["environments"]:
        raise ValueError(f'Unknown environment "{environment}". Call set_deploy_config first.')
    a = analyze(s)
    verified = [r["id"] for r in a["requirements"] if r["stage"] in ("verified", "deployed")]
    dep = compact({
        "id": next_id(s["deploy"]["history"], "DEP"),
        "environment": environment, "status": status, "version": version, "commit": commit, "url": url, "notes": notes,
        "at": now(),
        "requirement_revisions": {r["id"]: r["revision"] for r in s["requirements"] if r["id"] in verified},
    })
    s["deploy"]["history"].append(dep)
    log(s, "deploy", f"{dep['id']}: {environment} {status}" + (f" ({version})" if version else ""))
    return dep


def start_change(s, title, description="", type="feature"):
    one_of(type, ["feature", "fix", "refactor", "removal", "nfr"], "type")
    c = {
        "id": next_id(s["changes"], "CHG"),
        "title": title, "description": description, "type": type,
        "status": "open",
        "opened_at": now(),
        "closed_at": None,
        "impact": None,
        "summary": "",
    }
    s["changes"].append(c)
    s["current_change"] = c["id"]
    log(s, "change", f"{c['id']} opened: {title}")
    return c


def get_change(s, change_id=None):
    cid = change_id or s.get("current_change")
    c = next((x for x in s["changes"] if x["id"] == cid), None)
    if not c:
        raise ValueError(f"Unknown change {cid}" if cid else "No change is open. Call start_change first.")
    return c


def record_impact(s, change_id=None, requirement_ids=(), new_requirements=(), design_sections=(), files=(), tests=(), risks="", plan=""):
    c = get_change(s, change_id)
    assert_reqs(s, requirement_ids)
    c["impact"] = {
        "requirement_ids": list(requirement_ids), "new_requirements": list(new_requirements),
        "design_sections": list(design_sections), "files": list(files), "tests": list(tests),
        "risks": risks, "plan": plan, "at": now(),
    }
    log(s, "impact", f"{c['id']}: {len(requirement_ids)} requirement(s), {len(design_sections)} section(s), {len(files)} file(s)")
    return c


def complete_change(s, change_id=None, summary=""):
    c = get_change(s, change_id)
    c["status"] = "done"
    c["closed_at"] = now()
    c["summary"] = summary
    if s.get("current_change") == c["id"]:
        open_changes = [x for x in s["changes"] if x["status"] == "open"]
        s["current_change"] = open_changes[-1]["id"] if open_changes else None
    log(s, "change", f"{c['id']} completed")
    return c


# ---------------------------------------------------------------- analysis


def last_ok_deploy(s):
    return next((d for d in reversed(s["deploy"]["history"]) if d["status"] == "success"), None)


def analyze(s):
    """Derives every requirement's stage and what is missing or stale, plus the suggested next steps."""
    last_ok = last_ok_deploy(s)
    design_by = {}
    for name, sec in s["design"]["sections"].items():
        for rid in sec["requirement_ids"]:
            design_by.setdefault(rid, []).append(name)

    requirements = []
    for r in s["requirements"]:
        sections = design_by.get(r["id"], [])
        stale_sections = [n for n in sections if (s["design"]["sections"][n]["req_revisions"].get(r["id"]) or 0) < r["revision"]]
        files = s["code"]["links"].get(r["id"], [])
        criteria = []
        for c in r["acceptance_criteria"]:
            res = s["tests"]["criteria"].get(c["id"])
            status = "untested"
            if res:
                status = "stale" if res["req_revision"] < r["revision"] else res["status"]
            criteria.append(compact({"id": c["id"], "text": c["text"], "status": status, "test": res and res.get("test")}))
        all_pass = bool(criteria) and all(c["status"] == "pass" for c in criteria)
        deployed_rev = ((last_ok or {}).get("requirement_revisions") or {}).get(r["id"])
        if r["status"] == "retired":
            stage = "retired"
        elif r["status"] == "draft":
            stage = "draft"
        elif not sections or stale_sections:
            stage = "approved"
        elif not files:
            stage = "designed"
        elif not all_pass:
            stage = "implemented"
        elif deployed_rev == r["revision"]:
            stage = "deployed"
        else:
            stage = "verified"
        requirements.append({
            "id": r["id"], "title": r["title"], "priority": r["priority"], "status": r["status"], "revision": r["revision"],
            "stage": stage, "sections": sections, "staleSections": stale_sections, "files": files, "criteria": criteria,
        })

    active = [r for r in requirements if r["status"] == "approved"]
    drafts = [r["id"] for r in requirements if r["status"] == "draft"]
    undesigned = [r["id"] for r in active if not r["sections"]]
    stale_design = list(dict.fromkeys(x for r in active for x in r["staleSections"]))
    unimplemented = [r["id"] for r in active if r["sections"] and not r["files"]]
    crit = [(c, r) for r in active for c in r["criteria"]]
    failing = [c["id"] for c, _ in crit if c["status"] == "fail"]
    untested = [c["id"] for c, r in crit if c["status"] in ("untested", "stale") and r["files"]]
    changed_files = s["code"]["changed_files"]
    tests_stale = len(changed_files) > 0
    code_changed_since_deploy = bool(last_ok and s["code"].get("last_change_at") and s["code"]["last_change_at"] > last_ok["at"])
    undeployed = [r["id"] for r in active if r["stage"] == "verified"]

    blockers = []
    if not active:
        blockers.append("No approved requirements")
    if failing:
        blockers.append(f"Failing criteria: {', '.join(failing)}")
    must_unverified = [r["id"] for r in active if r["priority"] == "must" and r["stage"] not in ("verified", "deployed")]
    if must_unverified:
        blockers.append(f'"must" requirements not verified: {", ".join(must_unverified)}')
    if tests_stale:
        blockers.append(f"Code changed since the last green test run ({len(changed_files)} file(s))")
    if not s["deploy"]["environments"]:
        blockers.append("No deploy environment configured")

    open_change = next((c for c in s["changes"] if c["id"] == s.get("current_change")), None)
    nxt = []
    if open_change:
        nxt.append(f'Continue change {open_change["id"]} "{open_change["title"]}" (/app-lifecycle:change)')
    if not s["requirements"]:
        nxt.append("Capture requirements (/app-lifecycle:requirements)")
    if drafts:
        nxt.append(f"Review and approve draft requirements {', '.join(drafts)} (/app-lifecycle:requirements)")
    if undesigned or stale_design:
        targets = undesigned + ['section "%s"' % x for x in stale_design]
        nxt.append(f"Design {', '.join(targets)} (/app-lifecycle:design)")
    if unimplemented:
        nxt.append(f"Build {', '.join(unimplemented)} (/app-lifecycle:build)")
    if failing or untested or tests_stale:
        nxt.append("Run and update tests (/app-lifecycle:test)")
    if not blockers and (undeployed or code_changed_since_deploy or not last_ok):
        nxt.append("Deploy (/app-lifecycle:deploy)")
    if not nxt:
        nxt.append("Everything is verified and deployed. Use /app-lifecycle:change for the next change.")

    counts = {}
    for r in requirements:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1

    return {
        "project": s["project"],
        "counts": counts,
        "requirements": requirements,
        "gaps": {
            "drafts": drafts, "undesigned": undesigned, "stale_design_sections": stale_design, "unimplemented": unimplemented,
            "failing": failing, "untested": untested, "changed_files": changed_files, "undeployed": undeployed,
        },
        "tests_stale": tests_stale,
        "code_changed_since_deploy": code_changed_since_deploy,
        "last_test_run": s["tests"]["runs"][-1] if s["tests"]["runs"] else None,
        "last_deployment": s["deploy"]["history"][-1] if s["deploy"]["history"] else None,
        "open_change": open_change,
        "deploy_ready": not blockers,
        "deploy_blockers": blockers,
        "next_steps": nxt,
    }


def trace(s, requirement_id=None):
    a = analyze(s)
    rows = [r for r in a["requirements"] if r["id"] == requirement_id] if requirement_id else a["requirements"]
    if requirement_id and not rows:
        raise ValueError(f"Unknown requirement {requirement_id}")
    return [
        {
            **r,
            "decisions": [f"{d['id']} {d['title']} ({d['status']})" for d in s["design"]["decisions"] if r["id"] in d["requirement_ids"]],
            "changes": req_by_id(s, r["id"])["changes"],
        }
        for r in rows
    ]


def brief(s):
    """Short plain-text summary for the SessionStart hook."""
    a = analyze(s)
    stage_order = ["draft", "approved", "designed", "implemented", "verified", "deployed", "retired"]
    counts = ", ".join(f"{a['counts'][k]} {k}" for k in stage_order if a["counts"].get(k)) or "none yet"
    p = s["project"]
    lines = [
        "This project is managed with the app-lifecycle plugin. State: .lifecycle/state.json (read-only views: .lifecycle/*.md).",
        f"Project: {p['name']} ({p['kind']}{', ' + p['stack'] if p.get('stack') else ''}). {p['summary']}",
        f"Requirements: {counts}.",
    ]
    oc = a["open_change"]
    if oc:
        lines.append(f'Open change: {oc["id"]} "{oc["title"]}" ({"impact recorded" if oc.get("impact") else "impact not yet analysed"}).')
    run = a["last_test_run"]
    if run:
        lines.append(f"Last test run: {run['id']}, {run['passed']} passed / {run['failed']} failed ({run['at']}).")
    if a["tests_stale"]:
        lines.append(f"Tests are stale: {len(a['gaps']['changed_files'])} file(s) changed since the last green run.")
    d = a["last_deployment"]
    if d:
        lines.append(f"Last deployment: {d['id']} to {d['environment']}, {d['status']} ({d['at']}).")
    lines.append(f"Next steps: {'; '.join(a['next_steps'])}.")
    lines.append(
        "Rules: keep the lifecycle state in sync. Record requirement, design, code, test and deploy updates through the "
        "lifecycle MCP tools; never edit .lifecycle/ files by hand. For any change to an existing feature, use /app-lifecycle:change."
    )
    return "\n".join(lines)
