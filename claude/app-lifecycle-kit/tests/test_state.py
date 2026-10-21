# Unit tests for the lifecycle state engine: stages, staleness propagation and the change workflow.
# Run: python3 -m unittest discover -s tests
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import state as st  # noqa: E402


def tmpdir(prefix):
    return tempfile.mkdtemp(prefix=prefix)


def fresh():
    root = tmpdir("lifecycle-")
    st.init_project(root, name="Todo API", summary="Todos over HTTP", kind="api", stack="Node")
    return root


def stage_of(root, rid):
    return next(r for r in st.analyze(st.load(root))["requirements"] if r["id"] == rid)["stage"]


def build_one_requirement(root):
    st.mutate(root, lambda s: st.upsert_requirement(s, title="Create todo", acceptance_criteria=["returns 201", "rejects empty title"], status="approved"))
    st.mutate(root, lambda s: st.set_design_section(s, section="api", content="POST /todos", requirement_ids=["REQ-001"]))
    st.mutate(root, lambda s: st.link_code(root, s, requirement_ids=["REQ-001"], files=[os.path.join(root, "src/todos.js")]))
    st.track_edit(root, os.path.join(root, "src/todos.js"))


def green_run(root):
    return st.mutate(root, lambda s: st.record_test_run(
        s, command="npm test", passed=2, failed=0,
        results=[
            {"criterion_id": "REQ-001.AC1", "test": "t1", "status": "pass"},
            {"criterion_id": "REQ-001.AC2", "test": "t2", "status": "pass"},
        ],
    ))


class StateTest(unittest.TestCase):
    def test_init_creates_state_and_readable_views(self):
        root = fresh()
        for f in ["state.json", "REQUIREMENTS.md", "DESIGN.md", "TRACEABILITY.md", "HISTORY.md"]:
            self.assertTrue(os.path.exists(os.path.join(root, ".lifecycle", f)), f)
        with self.assertRaisesRegex(ValueError, "already exists"):
            st.init_project(root, name="again")

    def test_a_requirement_moves_through_every_stage_up_to_deployed(self):
        root = fresh()
        st.mutate(root, lambda s: st.upsert_requirement(s, title="Create todo", acceptance_criteria=["returns 201", "rejects empty title"]))
        self.assertEqual(stage_of(root, "REQ-001"), "draft")
        st.mutate(root, lambda s: st.upsert_requirement(s, id="REQ-001", status="approved"))
        self.assertEqual(stage_of(root, "REQ-001"), "approved")
        st.mutate(root, lambda s: st.set_design_section(s, section="api", content="POST /todos", requirement_ids=["REQ-001"]))
        self.assertEqual(stage_of(root, "REQ-001"), "designed")
        st.mutate(root, lambda s: st.link_code(root, s, requirement_ids=["REQ-001"], files=["./src/todos.js"]))
        self.assertEqual(stage_of(root, "REQ-001"), "implemented")
        green_run(root)
        self.assertEqual(stage_of(root, "REQ-001"), "verified")
        st.mutate(root, lambda s: st.set_deploy_config(s, target="local", environments=[{"name": "production", "deploy_command": "x"}]))
        self.assertTrue(st.analyze(st.load(root))["deploy_ready"])
        st.mutate(root, lambda s: st.record_deployment(s, environment="production", status="success", version="1.0.0"))
        self.assertEqual(stage_of(root, "REQ-001"), "deployed")

    def test_code_edits_make_tests_stale_and_block_deploy_until_a_green_run(self):
        root = fresh()
        build_one_requirement(root)
        st.mutate(root, lambda s: st.set_deploy_config(s, environments=[{"name": "production"}]))
        a = st.analyze(st.load(root))
        self.assertEqual(a["gaps"]["changed_files"], ["src/todos.js"])
        self.assertFalse(a["deploy_ready"])
        green_run(root)
        a = st.analyze(st.load(root))
        self.assertFalse(a["tests_stale"])
        self.assertTrue(a["deploy_ready"])

    def test_track_edit_ignores_lifecycle_files_outside_paths_and_non_lifecycle_projects(self):
        root = fresh()
        self.assertFalse(st.track_edit(root, os.path.join(root, ".lifecycle/state.json")))
        self.assertFalse(st.track_edit(root, "/etc/hosts"))
        plain = tmpdir("plain-")
        self.assertFalse(st.track_edit(plain, os.path.join(plain, "a.js")))
        self.assertFalse(os.path.exists(os.path.join(plain, ".lifecycle")))

    def test_changing_a_requirement_makes_its_design_tests_and_deployment_stale(self):
        root = fresh()
        build_one_requirement(root)
        green_run(root)
        st.mutate(root, lambda s: st.set_deploy_config(s, environments=[{"name": "production"}]))
        st.mutate(root, lambda s: st.record_deployment(s, environment="production", status="success"))
        self.assertEqual(stage_of(root, "REQ-001"), "deployed")

        st.mutate(root, lambda s: st.start_change(s, title="Titles max 100 chars", type="feature"))
        r = st.mutate(root, lambda s: st.upsert_requirement(
            s, id="REQ-001", acceptance_criteria=["returns 201", "rejects empty title", "rejects titles over 100 chars"]))
        self.assertEqual(r["revision"], 2)
        self.assertEqual(r["changes"], ["CHG-001"])

        a = st.analyze(st.load(root))
        self.assertEqual(a["gaps"]["stale_design_sections"], ["api"])
        self.assertEqual(stage_of(root, "REQ-001"), "approved")
        self.assertRegex(a["next_steps"][0], "CHG-001")

        st.mutate(root, lambda s: st.set_design_section(s, section="api", content="POST /todos (max 100)", requirement_ids=["REQ-001"]))
        self.assertEqual(stage_of(root, "REQ-001"), "implemented")  # old test results are stale at revision 2
        a = st.analyze(st.load(root))
        self.assertEqual([c["status"] for c in a["requirements"][0]["criteria"]], ["stale", "stale", "untested"])

        st.mutate(root, lambda s: st.record_test_run(
            s, command="npm test", passed=3, failed=0,
            results=[{"criterion_id": f"REQ-001.{x}", "test": x, "status": "pass"} for x in ["AC1", "AC2", "AC3"]],
        ))
        self.assertEqual(stage_of(root, "REQ-001"), "verified")  # verified, but revision 2 is not deployed yet
        st.mutate(root, lambda s: st.complete_change(s, summary="done"))
        self.assertIsNone(st.load(root)["current_change"])

    def test_a_failing_criterion_blocks_deploy_unknown_criteria_are_reported_not_stored(self):
        root = fresh()
        build_one_requirement(root)
        st.mutate(root, lambda s: st.set_deploy_config(s, environments=[{"name": "production"}]))
        res = st.mutate(root, lambda s: st.record_test_run(
            s, command="npm test", passed=1, failed=1,
            results=[
                {"criterion_id": "REQ-001.AC1", "test": "t1", "status": "pass"},
                {"criterion_id": "REQ-001.AC2", "test": "t2", "status": "fail"},
                {"criterion_id": "REQ-009.AC1", "test": "ghost", "status": "pass"},
            ],
        ))
        self.assertEqual(res["unknown_criteria"], ["REQ-009.AC1"])
        a = st.analyze(st.load(root))
        self.assertEqual(a["gaps"]["failing"], ["REQ-001.AC2"])
        self.assertFalse(a["deploy_ready"])

    def test_validation_errors_are_clear(self):
        root = fresh()
        with self.assertRaisesRegex(ValueError, "acceptance criterion"):
            st.mutate(root, lambda s: st.upsert_requirement(s, title="x"))
        with self.assertRaisesRegex(ValueError, "priority must be one of"):
            st.mutate(root, lambda s: st.upsert_requirement(s, title="x", acceptance_criteria=["a"], priority="urgent"))
        with self.assertRaisesRegex(ValueError, "Unknown requirement"):
            st.mutate(root, lambda s: st.set_design_section(s, section="api", content="", requirement_ids=["REQ-404"]))
        with self.assertRaisesRegex(ValueError, "set_deploy_config"):
            st.mutate(root, lambda s: st.record_deployment(s, environment="prod", status="success"))
        plain = tmpdir("plain-")
        with self.assertRaisesRegex(ValueError, "init_project"):
            st.mutate(plain, lambda s: None)

    def test_decisions_can_supersede_earlier_ones_brief_summarises_the_project(self):
        root = fresh()
        st.mutate(root, lambda s: st.record_decision(s, title="Use SQLite", decision="SQLite file DB"))
        st.mutate(root, lambda s: st.record_decision(s, title="Use Postgres", decision="Postgres", supersedes="DEC-001"))
        s = st.load(root)
        self.assertEqual(s["design"]["decisions"][0]["status"], "superseded by DEC-002")
        b = st.brief(s)
        self.assertRegex(b, "Project: Todo API")
        self.assertRegex(b, "Next steps: Capture requirements")


if __name__ == "__main__":
    unittest.main()
