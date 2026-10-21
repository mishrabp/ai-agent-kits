# Renders human-readable views of the lifecycle state into .lifecycle/*.md.
# They are regenerated on every save, so they always match state.json and read well in pull requests.
import os

BANNER = "> Generated from `state.json` by the app-lifecycle plugin. Don't edit this file; ask Claude to change the requirement, design or plan instead.\n"
ORDER = ["overview", "architecture", "components", "data_model", "api", "ui", "security", "non_functional", "deployment", "testing_strategy"]
STAGE_ICON = {"draft": "📝", "approved": "✅", "designed": "📐", "implemented": "🛠", "verified": "🧪", "deployed": "🚀", "retired": "🗄"}
CRIT_MARK = {"pass": "[x]", "fail": "[ ] ❌", "stale": "[ ] ⚠ stale", "untested": "[ ]", "skip": "[ ] skipped"}


def esc(t=""):
    return str(t).replace("|", "\\|").replace("\n", " ")


def title(k):
    return " ".join(w[:1].upper() + w[1:] for w in k.split("_"))


def when(iso):
    return iso[:16].replace("T", " ")


def requirements_md(s, a):
    by_id = {r["id"]: r for r in a["requirements"]}
    out = [f"# Requirements: {s['project']['name']}", "", BANNER, s["project"]["summary"], ""]
    out += ["| ID | Title | Type | Priority | Status | Stage | Rev |", "|---|---|---|---|---|---|---|"]
    for r in s["requirements"]:
        st = by_id[r["id"]]["stage"]
        kind = "NFR" if r["kind"] == "non_functional" else "Functional"
        out.append(f"| {r['id']} | {esc(r['title'])} | {kind} | {r['priority']} | {r['status']} | {STAGE_ICON.get(st, '')} {st} | {r['revision']} |")
    for r in s["requirements"]:
        ar = by_id[r["id"]]
        changes = f" · **Changes:** {', '.join(r['changes'])}" if r["changes"] else ""
        out += ["", f"## {r['id']}: {r['title']}", "",
                f"**Priority:** {r['priority']} · **Status:** {r['status']} · **Stage:** {ar['stage']} · **Revision:** {r['revision']}{changes}", ""]
        if r["description"]:
            out += [r["description"], ""]
        out += ["**Acceptance criteria**", ""]
        for c in ar["criteria"]:
            test = f" _(test: {c['test']})_" if c.get("test") else ""
            out.append(f"- {CRIT_MARK[c['status']]} **{c['id']}** {c['text']}{test}")
    return "\n".join(out) + "\n"


def design_md(s):
    out = [f"# Design: {s['project']['name']}", "", BANNER]
    sections = s["design"]["sections"]
    names = sorted(sections, key=lambda x: (ORDER.index(x) if x in ORDER else 99, x))
    if not names:
        out.append("_No design yet._")
    reqs = {r["id"]: r for r in s["requirements"]}
    for n in names:
        sec = sections[n]
        stale = [i for i in sec["requirement_ids"] if i in reqs and (sec["req_revisions"].get(i) or 0) < reqs[i]["revision"]]
        stale_note = f" · ⚠ **stale**: {', '.join(stale)} changed since this was written" if stale else ""
        covers = ", ".join(sec["requirement_ids"]) or "n/a"
        out += [f"## {title(n)}", "", f"_Covers: {covers} · revision {sec['revision']} · {sec['updated_at'][:10]}{stale_note}_", "",
                sec["content"].strip(), ""]
    if s["design"]["decisions"]:
        out += ["## Decisions", ""]
        for d in s["design"]["decisions"]:
            out += [f"### {d['id']}: {d['title']} ({d['status']}, {d['date']})", ""]
            if d.get("context"):
                out += [f"**Context:** {d['context']}", ""]
            out += [f"**Decision:** {d['decision']}", ""]
            if d.get("alternatives"):
                out += [f"**Alternatives considered:** {d['alternatives']}", ""]
            if d.get("consequences"):
                out += [f"**Consequences:** {d['consequences']}", ""]
            if d["requirement_ids"]:
                out += [f"_Requirements: {', '.join(d['requirement_ids'])}_", ""]
    return "\n".join(out) + "\n"


def traceability_md(s, a):
    out = [f"# Traceability: {s['project']['name']}", "", BANNER]
    out += ["| Requirement | Stage | Design | Code | Tests | Deployed |", "|---|---|---|---|---|---|"]
    last_ok = next((d for d in reversed(s["deploy"]["history"]) if d["status"] == "success"), None)
    for r in a["requirements"]:
        passed = sum(1 for c in r["criteria"] if c["status"] == "pass")
        dep = ((last_ok or {}).get("requirement_revisions") or {}).get(r["id"])
        design = ", ".join(f"{x} ⚠" if x in r["staleSections"] else x for x in r["sections"]) or "-"
        code = "<br>".join(f"`{f}`" for f in r["files"]) or "-"
        deployed = "-"
        if dep:
            deployed = f"{last_ok['id']} ✓" if dep == r["revision"] else f"{last_ok['id']} (old rev {dep})"
        out.append(f"| {r['id']} {esc(r['title'])} | {r['stage']} | {design} | {code} | {passed}/{len(r['criteria'])} | {deployed} |")
    out += ["", "## Status", ""]
    out.append(f"- Deploy ready: **{'yes' if a['deploy_ready'] else 'no'}**")
    out += [f"  - {b}" for b in a["deploy_blockers"]]
    if a["gaps"]["changed_files"]:
        out.append(f"- Changed since last green test run: {', '.join(f'`{f}`' for f in a['gaps']['changed_files'])}")
    out += ["", "## Next steps", ""] + [f"1. {n}" for n in a["next_steps"]]
    return "\n".join(out) + "\n"


def history_md(s):
    out = [f"# History: {s['project']['name']}", "", BANNER, "## Changes", ""]
    if not s["changes"]:
        out.append("_None yet._")
    for c in reversed(s["changes"]):
        closed = f", closed {c['closed_at'][:10]}" if c.get("closed_at") else ""
        out += [f"### {c['id']}: {c['title']} ({c['type']}, {c['status']})", "", f"Opened {c['opened_at'][:10]}{closed}.", ""]
        if c.get("description"):
            out += [c["description"], ""]
        i = c.get("impact")
        if i:
            new = f"; new: {'; '.join(i['new_requirements'])}" if i["new_requirements"] else ""
            out += [
                f"**Impact:** requirements {', '.join(i['requirement_ids']) or '-'}{new}; design {', '.join(i['design_sections']) or '-'}; "
                f"{len(i['files'])} file(s); tests: {', '.join(i['tests']) or '-'}",
                "",
            ]
            if i.get("plan"):
                out += [f"**Plan:** {i['plan']}", ""]
            if i.get("risks"):
                out += [f"**Risks:** {i['risks']}", ""]
        if c.get("summary"):
            out += [f"**Outcome:** {c['summary']}", ""]
    out += ["## Deployments", "", "| ID | When | Environment | Status | Version | Commit | URL |", "|---|---|---|---|---|---|---|"]
    for d in reversed(s["deploy"]["history"]):
        commit = d["commit"][:8] if d.get("commit") else "-"
        out.append(f"| {d['id']} | {when(d['at'])} | {d['environment']} | {d['status']} | {d.get('version') or '-'} | {commit} | {d.get('url') or '-'} |")
    out += ["", "## Test runs (latest 20)", "", "| ID | When | Passed | Failed | Command |", "|---|---|---|---|---|"]
    for r in reversed(s["tests"]["runs"][-20:]):
        out.append(f"| {r['id']} | {when(r['at'])} | {r['passed']} | {r['failed']} | `{esc(r['command'])}` |")
    return "\n".join(out) + "\n"


def render_all(d, s, a):
    files = {
        "REQUIREMENTS.md": requirements_md(s, a),
        "DESIGN.md": design_md(s),
        "TRACEABILITY.md": traceability_md(s, a),
        "HISTORY.md": history_md(s),
    }
    for name, text in files.items():
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
