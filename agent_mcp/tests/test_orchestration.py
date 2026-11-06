import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import orchestration
from task import Task, TaskRequest, TaskResult


class StartTaskTests(unittest.TestCase):
    def test_network_setup_applies_rules_without_audits_or_probes(self):
        with (patch.object(orchestration, "sbx") as sandbox,
              patch.object(orchestration, "run") as command):
            orchestration.configure_network("worker")
        sandbox.assert_not_called()
        command.assert_called_once()
        args = command.call_args.args
        self.assertEqual(args[:3], ("bash", "-e", "-c"))
        self.assertEqual(args[-1], "worker")
        self.assertIn('apply_network_rules "$1"', args[3])
        self.assertNotIn("policy ls", args[3])
        self.assertNotIn("curl", args[3])

    def test_empty_task_has_no_side_effects(self):
        with patch.object(orchestration, "sbx") as sandbox:
            with self.assertRaises(ValueError):
                orchestration.start(TaskRequest("  ", "test-model"))
            with self.assertRaisesRegex(ValueError, "model must not be empty"):
                TaskRequest("Task", " ")
            with self.assertRaisesRegex(ValueError, "reasoning_effort must not be empty"):
                TaskRequest("Task", "test-model", " ")
            self.assertIsNone(TaskRequest("Task", "test-model").reasoning_effort)
            sandbox.assert_not_called()

    def test_launch_uses_independent_git_and_worker_instructions(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo = root / "repo"
            repo.mkdir()
            orchestration.run("git", "init", str(repo))
            (repo / "agents.md").write_text("Host instructions")
            (repo / "sub-agent.md").write_text("Worker instructions")
            orchestration.run("git", "add", ".", cwd=repo)
            orchestration.run("git", "-c", "user.name=Test", "-c", "user.email=test@localhost",
                              "commit", "-m", "Baseline", cwd=repo)
            host_refs = orchestration.run("git", "show-ref", cwd=repo)
            host_worktrees = orchestration.run("git", "worktree", "list", "--porcelain", cwd=repo)
            process = Mock(pid=123)
            def sandbox_command(*args):
                if args[0] == "exec" and args[2:] == ("printenv", "HOME"):
                    return "/home/agent\n"
                return ""
            with (patch.object(orchestration, "REPOSITORY", repo),
                  patch.object(orchestration, "sbx", side_effect=sandbox_command) as sandbox,
                  patch.object(orchestration, "configure_network") as network,
                  patch.object(orchestration.threading, "Thread"),
                  patch.object(orchestration, "Popen", return_value=process) as launch):
                started = orchestration.start(TaskRequest('Implement a task; $(touch unexpected)', "test-model", "high"))
                self.assertIsInstance(started, Task)
                task_id = started.task_id
                self.assertEqual(started.pid, 123)
            task_dir = repo / "executions" / task_id
            self.assertEqual(task_dir.stat().st_mode & 0o777, 0o700)
            checkout = task_dir / "checkout"
            self.assertFalse((task_dir / "worktree").exists())
            self.assertEqual(orchestration.run("git", "show-ref", cwd=repo), host_refs)
            self.assertEqual(
                orchestration.run("git", "worktree", "list", "--porcelain", cwd=repo),
                host_worktrees,
            )
            self.assertEqual(
                orchestration.run("git", "branch", "--show-current", cwd=checkout).strip(),
                f"agent-task/{task_id}",
            )
            self.assertTrue((checkout / ".git").is_dir())
            self.assertFalse((checkout / ".git" / "objects" / "info" / "alternates").exists())
            self.assertEqual(orchestration.run("git", "remote", cwd=checkout), "")
            self.assertEqual(orchestration.run("git", "status", "--porcelain", cwd=checkout), "")
            self.assertEqual((checkout / "AGENTS.md").read_text(), "Worker instructions")
            self.assertFalse((checkout / "agent.md").exists())
            self.assertIn("$(touch unexpected)", (task_dir / "prompt.txt").read_text())
            self.assertNotIn("$(touch unexpected)", str(launch.call_args))
            record = json.loads((task_dir / "task.json").read_text())
            self.assertEqual(record["id"], task_id)
            self.assertEqual(record["state"], "launched")
            self.assertEqual(record["model"], "test-model")
            command = launch.call_args.args[0]
            self.assertEqual(command[command.index("--model") + 1], "test-model")
            self.assertEqual(command[command.index("-c", command.index("codex")) + 1], 'model_reasoning_effort="high"')
            self.assertEqual(record["reasoning_effort"], "high")
            worker_root = f"/home/agent/executions/{task_id}"
            self.assertEqual(record["workspace"], f"{worker_root}/task")
            self.assertEqual(record["delivery_directory"], f"{worker_root}/delivery")
            self.assertIn(f"{worker_root}/delivery", (task_dir / "prompt.txt").read_text())
            sandbox.assert_any_call("exec", record["sandbox"], "mkdir", "-p", f"{worker_root}/delivery")
            sandbox.assert_any_call("cp", str(checkout), f"{record['sandbox']}:{worker_root}/task")
            self.assertIn(f"{worker_root}/task", launch.call_args.args[0])
            self.assertNotIn("/workspace", str(sandbox.call_args_list) + str(launch.call_args))
            network.assert_called_once_with(record["sandbox"])
            self.assertFalse(any(call.args[0] == "policy" for call in sandbox.call_args_list))
            create = next(call for call in sandbox.call_args_list if call.args[0] == "create")
            self.assertIn("autonomous-agent:v1", create.args)
            self.assertNotIn(str(repo), create.args)

    def test_policy_failure_stops_sandbox_and_does_not_launch(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "sub-agent.md").write_text("Worker instructions")
            # Preparation is stubbed here; failure must occur before the process launch.
            def fake_run(*args, **kwargs):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir()
                return "base\n"
            with (patch.object(orchestration, "REPOSITORY", repo),
                  patch.object(orchestration, "run", side_effect=fake_run),
                  patch.object(orchestration, "sbx", return_value="default-deny-all") as sandbox,
                  patch.object(orchestration, "configure_network", side_effect=RuntimeError("policy")),
                  patch.object(orchestration, "Popen") as launch):
                with self.assertRaisesRegex(RuntimeError, "policy"):
                    orchestration.start(TaskRequest("Task", "test-model"))
            launch.assert_not_called()
            self.assertTrue(any(call.args[0] == "stop" for call in sandbox.call_args_list))
            directory, = (repo / "executions").iterdir()
            self.assertEqual(json.loads((directory / "task.json").read_text())["state"], "failed")


class TaskStatusTests(unittest.TestCase):
    def test_pid_liveness_before_and_after_process_exit(self):
        process = orchestration.Popen(["sleep", "30"])
        try:
            self.assertTrue(orchestration.pid_running(process.pid))
        finally:
            process.terminate()
            process.wait()
        self.assertFalse(orchestration.pid_running(process.pid))

    def test_status_rejects_mismatched_pid(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = "c" * 32
            record = Path(root) / "executions" / task_id / "task.json"
            record.parent.mkdir(parents=True)
            orchestration.save_record(record, {"id": task_id, "state": "launched", "pid": 123})
            with patch.object(orchestration, "REPOSITORY", Path(root)):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    orchestration.status(Task(task_id, 456))

    def test_invalid_and_unknown_ids(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(orchestration, "REPOSITORY", Path(root)):
                for invalid in ("../task", "", "/tmp/task", "a" * 33):
                    with self.assertRaisesRegex(ValueError, "Invalid task ID"):
                        Task(invalid, 123)
                with self.assertRaisesRegex(ValueError, "Unknown task ID"):
                    orchestration.status(Task("a" * 32, 123))
                for pid in (0, -1, True):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        Task("a" * 32, pid)

    def test_running_task_and_persisted_exit_states(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = "a" * 32
            record = Path(root) / "executions" / task_id / "task.json"
            record.parent.mkdir(parents=True)
            with patch.object(orchestration, "REPOSITORY", Path(root)):
                for code, expected in ((0, "completed"), (1, "failed"), (-15, "failed")):
                    metadata = {"id": task_id, "state": "launched", "pid": 123}
                    orchestration.save_record(record, metadata)
                    process = orchestration.Popen(["sh", "-c", f"exit {max(code, 0)}"])
                    # Negative return codes represent termination by a signal.
                    if code < 0:
                        process.wait()
                        process = Mock(wait=Mock(return_value=code))
                    orchestration.watch_task(process, record, metadata)
                    result = orchestration.status(Task(task_id, 123))
                    self.assertEqual(result["state"], expected)
                    self.assertEqual(result["exit_code"], code)

    def test_unmonitored_task_checks_pid(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = "b" * 32
            record = Path(root) / "executions" / task_id / "task.json"
            record.parent.mkdir(parents=True)
            metadata = {"id": task_id, "state": "launched", "pid": 123}
            orchestration.save_record(record, metadata)
            with (patch.object(orchestration, "REPOSITORY", Path(root)),
                  patch.object(orchestration, "pid_running", return_value=True) as alive):
                result = orchestration.status(Task(task_id, 123))
                self.assertEqual(result["state"], "launched")
                self.assertTrue(result["running"])
                alive.assert_called_once_with(123)
            with (patch.object(orchestration, "REPOSITORY", Path(root)),
                  patch.object(orchestration, "pid_running", return_value=False)):
                result = orchestration.status(Task(task_id, 123))
                self.assertEqual(result["state"], "failed")
                self.assertFalse(result["running"])
                self.assertIn("no longer running", result["error"])
            # Status does not overwrite a concurrent watcher's completion record.
            self.assertEqual(json.loads(record.read_text())["state"], "launched")


class DeliveryTests(unittest.TestCase):
    def test_result_retrieves_outputs_once_without_nested_delivery(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "sandbox-delivery"
            source.mkdir()
            (source / "worker.patch").write_text("diff --git a/example b/example\n")
            (source / "delivery-report.md").write_text("Completed with verification gaps.")
            (source / "junit.xml").write_text("<testsuites/>")
            task = Task("d" * 32, 123)
            record = root / "executions" / task.task_id / "task.json"
            record.parent.mkdir(parents=True)
            metadata = {"id": task.task_id, "pid": task.pid, "state": "completed",
                        "sandbox": "worker", "delivery_directory": "/home/agent/delivery"}
            orchestration.save_record(record, metadata)
            def copy(*args):
                self.assertEqual(args[:2], ("cp", "worker:/home/agent/delivery"))
                shutil.copytree(source, args[2])
                return ""
            with (patch.object(orchestration, "REPOSITORY", root),
                  patch.object(orchestration, "sbx", side_effect=copy) as sandbox):
                delivered = orchestration.result(task)
                self.assertIsInstance(delivered, TaskResult)
                self.assertEqual(delivered.files, ["delivery-report.md", "junit.xml", "worker.patch"])
                self.assertEqual(delivered.patch_file, str(record.parent / "delivery" / "worker.patch"))
                self.assertEqual(delivered.report_file, str(record.parent / "delivery" / "delivery-report.md"))
                self.assertEqual(orchestration.result(task), delivered)
                sandbox.assert_called_once()
                Path(delivered.patch_file).unlink()
                Path(delivered.report_file).unlink()
                missing = orchestration.result(task)
                self.assertIsNone(missing.patch_file)
                self.assertIsNone(missing.report_file)

    def test_retrieval_failure_preserves_exit_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as root:
            record = Path(root) / "task.json"
            metadata = {"state": "launched", "sandbox": "worker", "delivery_directory": "/delivery"}
            with patch.object(orchestration, "sbx", side_effect=RuntimeError("copy failed")):
                orchestration.watch_task(Mock(wait=Mock(return_value=0)), record, metadata)
            saved = json.loads(record.read_text())
            self.assertEqual(saved["state"], "completed")
            self.assertEqual(saved["exit_code"], 0)
            self.assertIn("copy failed", saved["delivery_error"])
            self.assertFalse((Path(root) / "delivery").exists())
            self.assertEqual(list(Path(root).glob(".delivery-*")), [])


if __name__ == "__main__":
    unittest.main()
