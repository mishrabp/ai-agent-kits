# The "lifecycle" MCP server: the only writer of .lifecycle/state.json during a session.
import state as st
from mcp_stdio import Server

VERSION = "1.0.0"


def string(description=None, **extra):
    return {"type": "string", **({"description": description} if description else {}), **extra}


def integer(**extra):
    return {"type": "integer", **extra}


def array(items, description=None):
    return {"type": "array", "items": items, **({"description": description} if description else {})}


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


IDS = array(string(), 'Requirement ids, e.g. ["REQ-001"]')


def create_server(root=None):
    root = root or st.project_dir()
    server = Server("app-lifecycle", VERSION)

    def tool(name, description, properties=None, required=(), write=True):
        """Registers a handler. Errors become tool errors, and every write returns the fresh next steps."""

        def register(fn):
            def handler(**args):
                result = fn(**args)
                if not write:
                    return result
                s = st.load(root)
                return {"result": result, "next_steps": st.analyze(s)["next_steps"] if s else []}

            server.tool(name, description, properties, required,
                        annotations={"readOnlyHint": not write, "destructiveHint": False, "openWorldHint": False})(handler)
            return fn

        return register

    def loaded():
        s = st.load(root)
        if not s:
            raise ValueError("No lifecycle project here. Call init_project first.")
        return s

    @tool("status",
          "Project dashboard: each requirement's stage (draft, approved, designed, implemented, verified, deployed), gaps, stale items, deploy readiness and suggested next steps. Call this first in every lifecycle task.",
          write=False)
    def status():
        s = st.load(root)
        if not s:
            return {"initialized": False, "project_dir": root,
                    "next_steps": ["Call init_project, then capture requirements (/app-lifecycle:requirements)"]}
        a = st.analyze(s)
        reqs = []
        for r in a["requirements"]:
            passed = sum(1 for c in r["criteria"] if c["status"] == "pass")
            reqs.append({**r, "criteria": f"{passed}/{len(r['criteria'])} pass"})
        return {"initialized": True, "project_dir": root, **a, "requirements": reqs}

    @tool("get_state",
          "Read part of the raw lifecycle state: project, requirements, design, code, tests, deploy, changes, or log.",
          {"part": string(enum=["project", "requirements", "design", "code", "tests", "deploy", "changes", "log"])},
          required=["part"], write=False)
    def get_state(part):
        s = loaded()
        return s["log"][-50:] if part == "log" else s[part]

    @tool("trace",
          "Traceability for one requirement (or all of them): design sections, decisions, code files, per-criterion test status, deployment, and the changes that touched it. Use it for impact analysis.",
          {"requirement_id": string()}, write=False)
    def trace(requirement_id=None):
        return st.trace(loaded(), requirement_id)

    @tool("init_project", "Create the lifecycle state (.lifecycle/) for this project. Only once per project.",
          {
              "name": string(),
              "summary": string("One or two sentences: what the product is and who it is for"),
              "kind": string(enum=["web_app", "api", "mobile_app", "desktop_app", "cli", "library", "other"]),
              "stack": string("Chosen or preferred tech stack, if known"),
          },
          required=["name", "summary", "kind"])
    def init_project(**a):
        return st.init_project(root, **a)

    @tool("update_project", "Update the project's name, summary, kind or stack.",
          {"name": string(), "summary": string(), "kind": string(), "stack": string()})
    def update_project(**a):
        return st.mutate(root, lambda s: st.update_project(s, **a))

    @tool("upsert_requirement",
          "Add a requirement (omit id) or update one (pass id). Acceptance criteria must be testable; they get ids like REQ-001.AC1. Changing title, description or criteria raises the revision, which marks linked design, tests and deployment as stale.",
          {
              "id": string(),
              "title": string(),
              "description": string("User story: As a <user>, I want <goal> so that <benefit>. Plus any detail."),
              "kind": string(enum=["functional", "non_functional"]),
              "priority": string(enum=["must", "should", "could"]),
              "status": string(enum=["draft", "approved", "retired"]),
              "acceptance_criteria": array(string(), "Full list (replaces the old one). Given/When/Then style."),
          })
    def upsert_requirement(**a):
        return st.mutate(root, lambda s: st.upsert_requirement(s, **a))

    @tool("set_design_section",
          f"Create or replace a design section and record which requirements it covers. Standard sections: {', '.join(st.DESIGN_SECTIONS)}.",
          {"section": string(), "content": string("Markdown"), "requirement_ids": IDS},
          required=["section", "content", "requirement_ids"])
    def set_design_section(**a):
        return st.mutate(root, lambda s: st.set_design_section(s, **a))

    @tool("record_decision",
          "Record an architecture or design decision (ADR style). Use supersedes to replace an earlier decision.",
          {
              "title": string(), "decision": string(),
              "context": string(), "alternatives": string(), "consequences": string(),
              "requirement_ids": IDS, "supersedes": string("e.g. DEC-002"),
          },
          required=["title", "decision"])
    def record_decision(**a):
        return st.mutate(root, lambda s: st.record_decision(s, **a))

    @tool("link_code", "Record which source files implement which requirements (paths relative to the project root).",
          {"requirement_ids": IDS, "files": array(string())}, required=["requirement_ids", "files"])
    def link_code(**a):
        return st.mutate(root, lambda s: st.link_code(root, s, **a))

    @tool("unlink_code", "Remove files from a requirement's code links (for example after a file is deleted or moved).",
          {"requirement_id": string(), "files": array(string())}, required=["requirement_id", "files"])
    def unlink_code(**a):
        return st.mutate(root, lambda s: st.unlink_code(root, s, **a))

    @tool("record_test_run",
          "Record the result of a full test-suite run, with a per-acceptance-criterion result for every criterion that a test covers. A run with failed=0 clears the 'changed since last test' list.",
          {
              "command": string(), "passed": integer(), "failed": integer(), "skipped": integer(),
              "results": array(obj({
                  "criterion_id": string("e.g. REQ-001.AC2"),
                  "test": string("Test file and name"),
                  "status": string(enum=["pass", "fail", "skip"]),
              }, required=["criterion_id", "test", "status"])),
              "commit": string(), "notes": string(),
          },
          required=["command", "passed", "failed", "results"])
    def record_test_run(**a):
        return st.mutate(root, lambda s: st.record_test_run(s, **a))

    @tool("set_deploy_config",
          "Set the deploy target and environments. Each environment has its build and deploy commands, URL, smoke check and rollback command.",
          {
              "target": string("e.g. docker, vercel, fly, azure-app-service, cloud-run, kubernetes, local"),
              "environments": array(obj({
                  "name": string(), "build_command": string(), "deploy_command": string(),
                  "url": string(), "smoke_check": string(), "rollback_command": string(), "notes": string(),
              }, required=["name"])),
          })
    def set_deploy_config(**a):
        return st.mutate(root, lambda s: st.set_deploy_config(s, **a))

    @tool("record_deployment",
          "Record a deployment attempt. A success marks every verified requirement as deployed at its current revision.",
          {
              "environment": string(), "status": string(enum=["success", "failed", "rolled_back"]),
              "version": string(), "commit": string(), "url": string(), "notes": string(),
          },
          required=["environment", "status"])
    def record_deployment(**a):
        return st.mutate(root, lambda s: st.record_deployment(s, **a))

    @tool("start_change",
          "Open a change request for an incremental change to an existing app. It becomes the current change, and requirement edits are tagged with it.",
          {"title": string(), "description": string(), "type": string(enum=["feature", "fix", "refactor", "removal", "nfr"])},
          required=["title"])
    def start_change(**a):
        return st.mutate(root, lambda s: st.start_change(s, **a))

    @tool("record_impact",
          "Record the impact analysis for a change: affected requirements, new requirements, design sections, files and tests, plus the plan and risks.",
          {
              "change_id": string(), "requirement_ids": IDS, "new_requirements": array(string()),
              "design_sections": array(string()), "files": array(string()), "tests": array(string()),
              "plan": string(), "risks": string(),
          })
    def record_impact(**a):
        return st.mutate(root, lambda s: st.record_impact(s, **a))

    @tool("complete_change", "Close a change request with a short summary of what changed.",
          {"change_id": string(), "summary": string()})
    def complete_change(**a):
        return st.mutate(root, lambda s: st.complete_change(s, **a))

    return server


def run_mcp():
    create_server().run()
