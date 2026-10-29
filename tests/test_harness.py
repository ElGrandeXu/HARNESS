"""Real local CLI tests in isolated copies; never calls a model or provider API."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit
import re

SOURCE = Path(__file__).resolve().parents[1]


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        self.root.mkdir()
        # Copy template assets only, never a student's already-adapted data.
        for name in ("scripts", "templates", "profiles", "examples", "docs"):
            shutil.copytree(SOURCE / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("AGENTS.md", "CLAUDE.md", "START_HERE.md", ".gitignore"):
            shutil.copy2(SOURCE / name, self.root / name)
        self.cli = self.root / "scripts/harness.py"
        self.run_cli("init")

    def run_cli(self, *args, expected=0, env=None, input=None):
        proc = subprocess.run([sys.executable, str(self.cli), *args], cwd=self.temp.name,
                              capture_output=True, text=True, env=env, input=input, timeout=30)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return proc

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def revision(self, name):
        return self.run_cli("revision", name).stdout.strip()

    def note(self, identifier="MEM-001", kind="fact", statement="Un fait de test.", scope="test"):
        meta = {"id": identifier, "type": kind, "status": "accepted" if kind == "decision" else "observed",
                "scope": scope, "statement": statement, "reason": "test fixture",
                "source": ["examples/BRIEF-demo.md"], "evidence": ["examples/BRIEF-demo.md"],
                "last_verified": "2026-10-29", "review_when": "changement du brief", "supersedes": []}
        return "---\n" + json.dumps(meta) + "\n---\n\n# Note fixture\n"

    def make_task(self):
        return self.run_cli("task", "--id", "TASK-001", "--goal", "Catalogue valide", "--scope", "catalogue.csv",
                            "--owner", "fixture", "--acceptance", "Deux livres et colonnes titre,auteur",
                            "--verification", "contrôle CSV").stdout.strip()

    def hook(self, event, env=None):
        return subprocess.run([sys.executable, str(self.root / "profiles/claude/bootstrap.py")],
                              input=json.dumps(event), text=True, capture_output=True,
                              cwd=self.temp.name, env=env, timeout=10)

    def test_clean_init_and_second_init_preserve_customization(self):
        self.assertFalse(list((self.root / "tasks").glob("TASK-*.md")))
        self.assertFalse(list((self.root / "memory").glob("**/MEM-*.md")))
        self.assertFalse(list((self.root / "handoffs/sessions").glob("SESSION-*.md")))
        self.write("memory/MEMORY.md", "# Index personnalisé\n")
        self.write("project.local.json", '{"custom": true}')
        result = json.loads(self.run_cli("init").stdout)
        self.assertEqual(result["created"], [])
        self.assertEqual((self.root / "memory/MEMORY.md").read_text(encoding="utf-8"), "# Index personnalisé\n")
        self.assertEqual((self.root / "project.local.json").read_text(encoding="utf-8"), '{"custom": true}')
        self.run_cli("validate")

    def test_explicit_root_independent_of_cwd(self):
        self.run_cli("--root", str(self.root), "validate")

    def test_doctor_without_llm_or_git(self):
        env = dict(os.environ, PATH="")
        result = json.loads(self.run_cli("doctor", env=env).stdout)
        self.assertFalse(result["optional_cli"]["codex"]["available"])
        self.assertFalse(result["optional_cli"]["claude"]["available"])
        self.assertEqual(result["local_errors"], [])

    def test_inputs_and_generated_data_ignored_by_git(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("Git optional and unavailable")
        subprocess.run([git, "init", str(self.root)], check=True, capture_output=True)
        for name in ("inbox/private.md", "memory/MEMORY.md", "memory/topics/MEM-test.md",
                     "tasks/TASK-001.md", "handoffs/CURRENT.md", ".agent-state/evidence/test.json",
                     "project.local.json", "CLAUDE.local.md", "AGENTS.local.md", ".delivery/log.txt"):
            result = subprocess.run([git, "-C", str(self.root), "check-ignore", name], capture_output=True)
            self.assertEqual(result.returncode, 0, name)
        result = subprocess.run([git, "-C", str(self.root), "check-ignore", "inbox/README.md"], capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_inventory_does_not_read_contents(self):
        self.write("inbox/BRIEF.md", "private fixture content\n")
        proc = self.run_cli("inventory")
        self.assertNotIn("private fixture content", proc.stdout)
        self.assertIn('"content_loaded": false', proc.stdout)

    def test_bounded_read_and_ingestion_provenance(self):
        self.write("inbox/brief.md", "\n".join(f"line {i}" for i in range(300)))
        selected = json.loads(self.run_cli("read", "inbox/brief.md", "--start", "12", "--lines", "3").stdout)
        self.assertEqual(selected["text"], "line 11\nline 12\nline 13")
        receipt = self.run_cli("ingest", "inbox/brief.md").stdout.strip()
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual(len(data["excerpt"]), 200)
        self.assertTrue(data["truncated"])
        self.assertEqual(data["confirmed_decisions"], [])
        self.assertEqual(len(data["sha256"]), 64)

    def test_unsupported_or_oversize_ingestion(self):
        self.write("inbox/file.pdf", "not a real PDF")
        self.run_cli("ingest", "inbox/file.pdf", expected=1)
        self.write("inbox/large.md", "a" * 65537)
        self.run_cli("ingest", "inbox/large.md", expected=1)
        self.assertFalse((self.root / ".agent-state/ingestion").exists())

    def test_index_too_long_and_context_bounded(self):
        for text in ("abc\n" * 81, "a" * 8193):
            with self.subTest(size=len(text)):
                self.write("memory/MEMORY.md", text)
                self.assertIn("Taille excessive", self.run_cli("validate", expected=1).stderr)
        self.write("memory/MEMORY.md", "abc\n" * 100000)
        proc = self.run_cli("validate", expected=1)
        self.assertIn("Taille excessive", proc.stderr)
        context = self.run_cli("context").stdout
        self.assertIn("TRONQUÉ", context)
        self.assertLess(len(context.encode()), 18000)

    def test_broken_local_link(self):
        self.write("memory/MEMORY.md", "# Index\n\n[missing](topics/missing.md)\n")
        self.assertIn("Lien cassé", self.run_cli("validate", expected=1).stderr)

    def test_duplicate_id_even_in_archive(self):
        self.write("memory/topics/one.md", self.note())
        self.write("memory/archive/two.md", self.note())
        self.assertIn("dupliqué", self.run_cli("validate", expected=1).stderr)

    def test_required_source_and_type_status(self):
        note = self.note().replace('"source": ["examples/BRIEF-demo.md"]', '"source": []')
        self.write("memory/topics/one.md", note)
        self.assertIn("Sources", self.run_cli("validate", expected=1).stderr)
        self.write("memory/topics/one.md", self.note().replace('"status": "observed"', '"status": "accepted"'))
        self.assertIn("Confusion", self.run_cli("validate", expected=1).stderr)

    def test_invalid_scalar_field_has_useful_diagnostic(self):
        self.write("memory/topics/one.md", self.note().replace('"statement": "Un fait de test."', '"statement": 42'))
        result = self.run_cli("validate", expected=1)
        self.assertIn("Champ texte", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_crlf_and_utf8_bom_metadata_preserves_raw_revision(self):
        data = ("\ufeff" + self.note()).replace("\n", "\r\n").encode("utf-8")
        path = self.root / "memory/topics/windows.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.run_cli("validate")
        import hashlib
        self.assertEqual(self.revision("memory/topics/windows.md"), hashlib.sha256(data).hexdigest())

    def test_context_deduplication_per_generation(self):
        first = self.run_cli("context", "--session", "one").stdout
        self.assertEqual(first.count("HARNESS_CONTEXT_V1"), 1)
        self.assertNotIn("HARNESS_CONTEXT_V1", self.run_cli("context", "--session", "one").stdout)
        self.assertIn("HARNESS_CONTEXT_V1", self.run_cli("context", "--session", "two").stdout)

    def test_lock_refuses_competing_writer(self):
        lock = self.root / ".agent-state/write.lock"
        lock.mkdir()
        try:
            self.assertIn("verrouillée", self.run_cli("init", expected=1).stderr)
        finally:
            lock.rmdir()

    def test_put_compare_and_swap_and_accepted_decision_immutable(self):
        self.write(".agent-state/draft.md", self.note(kind="decision"))
        self.run_cli("put", "memory/decisions/one.md", "--source", ".agent-state/draft.md", "--expected", "absent")
        self.run_cli("put", "memory/decisions/one.md", "--source", ".agent-state/draft.md", "--expected", "absent", expected=1)
        old = self.revision("memory/decisions/one.md")
        self.write(".agent-state/draft.md", self.note(kind="decision") + "Body silently changed\n")
        self.assertIn("immuable", self.run_cli("put", "memory/decisions/one.md", "--source", ".agent-state/draft.md", "--expected", old, expected=1).stderr)
        self.run_cli("put", "AGENTS.md", "--source", ".agent-state/draft.md", "--expected", "absent", expected=1)
        self.assertEqual(self.revision("memory/decisions/one.md"), old)

    def test_traversal_and_symlink_rejected(self):
        self.run_cli("read", "../outside.md", expected=1)
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("fixture")
        link = self.root / "inbox/link.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this platform")
        self.assertIn("symbolique", self.run_cli("read", "inbox/link.md", expected=1).stderr)

    def test_done_requires_evidence(self):
        relative = self.make_task()
        text = (self.root / relative).read_text(encoding="utf-8").replace('"status": "todo"', '"status": "done"')
        self.write(".agent-state/task.md", text)
        self.assertIn("sans preuve", self.run_cli("put", relative, "--source", ".agent-state/task.md",
                       "--expected", self.revision(relative), expected=1).stderr)

    def test_verification_errors_and_timeout_leave_receipts(self):
        failed = json.loads(self.run_cli("verify", "--", sys.executable, "-c", "raise SystemExit(7)", expected=1).stdout)
        self.assertEqual(failed["returncode"], 7)
        timeout = json.loads(self.run_cli("verify", "--timeout", "1", "--", sys.executable, "-c", "import time; time.sleep(3)", expected=1).stdout)
        self.assertEqual(timeout["returncode"], 124)
        absent = json.loads(self.run_cli("verify", "--", "definitely-unavailable-harness-fixture-cli", expected=1).stdout)
        self.assertEqual(absent["returncode"], 127)
        for result in (failed, timeout, absent):
            self.assertTrue((self.root / result["evidence"]).is_file())

    def test_fictional_project_ingestion_task_proof_and_resume(self):
        self.write("inbox/BRIEF.md", (self.root / "examples/BRIEF-demo.md").read_text(encoding="utf-8"))
        self.run_cli("ingest", "inbox/BRIEF.md")
        relative = self.make_task()
        self.write("catalogue.csv", "titre,auteur\nLivre A,Auteur A\nLivre B,Auteur B\n")
        self.write("check_catalogue.py", "import csv\nfrom pathlib import Path\nrows=list(csv.DictReader(Path('catalogue.csv').open(encoding='utf-8')))\nassert len(rows)>=2\nassert set(rows[0])=={'titre','auteur'}\nassert all(row['titre'] and row['auteur'] for row in rows)\n")
        receipt = json.loads(self.run_cli("verify", "--", sys.executable, "check_catalogue.py").stdout)["evidence"]
        text = (self.root / relative).read_text(encoding="utf-8")
        text = text.replace('"status": "todo"', '"status": "done"').replace('"evidence": []', '"evidence": ["' + receipt + '"]')
        self.write(".agent-state/task-draft.md", text)
        self.run_cli("put", relative, "--source", ".agent-state/task-draft.md", "--expected", self.revision(relative))
        old = self.revision("handoffs/CURRENT.md")
        checkpoint = json.loads(self.run_cli("checkpoint", "--expected", old, "--task", "TASK-001",
                    "--summary", "Catalogue CSV contrôlé", "--next", "Relire les titres avec l'utilisateur", "--evidence", receipt).stdout)
        self.assertTrue((self.root / checkpoint["session"]).is_file())
        fresh_context = self.run_cli("context").stdout
        self.assertIn("TASK-001", fresh_context)
        self.assertIn("Relire les titres", fresh_context)
        self.assertIn("périmé", self.run_cli("checkpoint", "--expected", old, "--summary", "stale", "--next", "no", expected=1).stderr)
        self.run_cli("validate")
        # The control is meaningful: invalid data fails the SAME command.
        self.write("catalogue.csv", "wrong\nbad\n")
        self.run_cli("verify", "--", sys.executable, "check_catalogue.py", expected=1)

    def test_consolidation_preserves_memory_flags_conflicts_and_detects_stale(self):
        self.write("memory/topics/one.md", self.note("MEM-001", statement="Le format est CSV."))
        self.write("memory/topics/two.md", self.note("MEM-002", statement="Le format est JSON."))
        before = {p: self.revision(p) for p in ("memory/MEMORY.md", "memory/topics/one.md", "memory/topics/two.md", "AGENTS.md")}
        relative = self.run_cli("consolidate", "--source", "memory/topics/one.md", "--source", "memory/topics/two.md").stdout.strip()
        data = json.loads((self.root / relative).read_text(encoding="utf-8"))
        self.assertFalse(data["llm_used"])
        self.assertEqual(data["changes"], [])
        self.assertEqual(len(data["potential_conflicts"]), 1)
        for p, sha in before.items():
            self.assertEqual(self.revision(p), sha)
        self.run_cli("proposal-check", relative)
        self.write("memory/topics/three.md", self.note("MEM-003"))
        self.assertIn("périmée", self.run_cli("proposal-check", relative, expected=1).stderr)

    def test_snapshot_tampering_and_missing_source_fail(self):
        self.write("inbox/brief.md", "Source fixture")
        self.run_cli("consolidate", expected=1)
        self.run_cli("consolidate", "--source", "inbox/missing.md", expected=1)
        relative = self.run_cli("consolidate", "--source", "inbox/brief.md").stdout.strip()
        proposal = json.loads((self.root / relative).read_text(encoding="utf-8"))
        snapshot = proposal["sources"]["inbox/brief.md"]["snapshot"]
        self.write(snapshot, "tampered")
        self.assertIn("altéré", self.run_cli("proposal-check", relative, expected=1).stderr)

    def test_malformed_proposal_schema_has_no_traceback(self):
        self.write("inbox/brief.md", "fixture")
        relative = self.run_cli("consolidate", "--source", "inbox/brief.md").stdout.strip()
        proposal = json.loads((self.root / relative).read_text(encoding="utf-8"))
        proposal["sources"] = []
        self.write(relative, json.dumps(proposal))
        result = self.run_cli("proposal-check", relative, expected=1)
        self.assertIn("Schéma", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_proposal_cannot_rewrite_stable_rules(self):
        self.write("inbox/brief.md", "fixture")
        relative = self.run_cli("consolidate", "--source", "inbox/brief.md").stdout.strip()
        proposal = json.loads((self.root / relative).read_text(encoding="utf-8"))
        proposal["changes"] = [{"path": "AGENTS.md", "before_sha256": self.revision("AGENTS.md"),
            "after": "changed", "reason": "fixture", "sources": ["inbox/brief.md"], "status": "proposed"}]
        self.write(relative, json.dumps(proposal))
        self.assertIn("memory", self.run_cli("proposal-check", relative, expected=1).stderr)

    def test_proposal_validates_virtual_note_and_index_without_writing(self):
        self.write("inbox/brief.md", "fixture")
        relative = self.run_cli("consolidate", "--source", "inbox/brief.md").stdout.strip()
        proposal = json.loads((self.root / relative).read_text(encoding="utf-8"))
        proposal["changes"] = [
            {"path": "memory/topics/new.md", "before_sha256": "absent", "after": self.note(),
             "reason": "fixture", "sources": ["inbox/brief.md"], "status": "proposed"},
            {"path": "memory/MEMORY.md", "before_sha256": self.revision("memory/MEMORY.md"),
             "after": "# Index\n\n[Note](topics/new.md)\n", "reason": "fixture",
             "sources": ["inbox/brief.md"], "status": "proposed"}]
        self.write(relative, json.dumps(proposal))
        self.run_cli("proposal-check", relative)
        self.assertFalse((self.root / "memory/topics/new.md").exists())

    def test_proposal_cannot_modify_accepted_decision(self):
        self.write("memory/decisions/one.md", self.note(kind="decision"))
        relative = self.run_cli("consolidate", "--source", "memory/decisions/one.md").stdout.strip()
        proposal = json.loads((self.root / relative).read_text(encoding="utf-8"))
        proposal["changes"] = [{"path": "memory/decisions/one.md", "before_sha256": self.revision("memory/decisions/one.md"),
            "after": self.note(kind="decision") + "new body", "reason": "fixture",
            "sources": ["memory/decisions/one.md"], "status": "proposed"}]
        self.write(relative, json.dumps(proposal))
        self.assertIn("acceptée", self.run_cli("proposal-check", relative, expected=1).stderr)

    def test_hook_valid_event_deduplicates_and_does_not_call_subprocess(self):
        event = {"hook_event_name": "SessionStart", "session_id": "fixture-session", "source": "startup"}
        env = dict(os.environ, PATH="", CLAUDE_PROJECT_DIR=str(self.root))
        first = self.hook(event, env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        context = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context.count("HARNESS_CONTEXT_V1"), 1)
        self.assertLess(len(context), 10000)
        self.assertEqual(self.hook(event, env=env).stdout, "")
        event["source"] = "resume"
        self.assertEqual(self.hook(event, env=env).stdout, "")
        self.assertNotIn("Stop", json.loads((self.root / "profiles/claude/settings.example.json").read_text(encoding="utf-8"))["hooks"])

    def test_hook_errors_fail_open_no_recursion(self):
        result = self.hook({"hook_event_name": "Stop", "stop_hook_active": True})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("SessionStart", result.stderr)
        # Malformed JSON also fails open rather than spawning another agent.
        result = subprocess.run([sys.executable, str(self.root / "profiles/claude/bootstrap.py")],
                                input="{", text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_hook_compaction_reinjects_with_changed_transcript(self):
        transcript = Path(self.temp.name) / "fixture-transcript.jsonl"
        transcript.write_text("first\n")
        event = {"hook_event_name": "SessionStart", "session_id": "fixture", "source": "compact", "transcript_path": str(transcript)}
        self.assertIn("HARNESS_CONTEXT_V1", self.hook(event).stdout)
        self.assertEqual(self.hook(event).stdout, "")
        transcript.write_text("second, changed transcript\n")
        self.assertIn("HARNESS_CONTEXT_V1", self.hook(event).stdout)

    def test_doctor_mocked_cli_failure_is_labelled(self):
        spec = importlib.util.spec_from_file_location("harness_fixture", self.cli)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.shutil, "which", return_value="fixture-cli"), \
             mock.patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture-cli", 10)), \
             mock.patch("builtins.print") as output:
            result = module.doctor(None)
        self.assertEqual(result, 0)
        data = json.loads(output.call_args.args[0])
        self.assertIn("diagnostic", data["optional_cli"]["claude"])


class PublicFilesTest(unittest.TestCase):
    def test_documentation_local_links(self):
        for folder in (SOURCE, SOURCE / "docs", SOURCE / "examples"):
            paths = folder.glob("*.md") if folder == SOURCE else folder.rglob("*.md")
            for path in paths:
                text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
                for ref in re.findall(r"\[[^\]]*\]\(([^\n)]+)\)", text):
                    parsed = urlsplit(ref.strip("<>"))
                    if parsed.scheme or not parsed.path:
                        continue
                    self.assertTrue((path.parent / unquote(parsed.path)).exists(), f"{path.name}: {ref}")


if __name__ == "__main__":
    unittest.main()
