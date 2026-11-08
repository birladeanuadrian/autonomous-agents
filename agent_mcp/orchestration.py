"""Host-side task preparation; worker checkouts never reference host Git metadata."""

import fcntl
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path, PurePosixPath
from subprocess import Popen

from task import CleanupResult, ExecutionSummary, Task, TaskRequest, TaskResult

REPOSITORY = Path(__file__).resolve().parents[1]
TEMPLATE = "autonomous-agent:v1"


def save_record(record: Path, metadata: dict) -> None:
    """Replace the record atomically so readers never see partial JSON."""
    temporary = record.with_name(f".task-{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(metadata, indent=2))
        temporary.replace(record)
    finally:
        temporary.unlink(missing_ok=True)


def watch_task(process: Popen, record: Path, metadata: dict) -> None:
    try:
        exit_code = process.wait()
    except Exception as error:
        metadata.update(state="unknown", error=f"Process monitoring failed: {error}")
        save_record(record, metadata)
        return
    try:
        lock = (record.parent / ".cleanup.lock").open("a")
    except FileNotFoundError:
        return  # A completed cleanup may already have deleted the execution.
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not record.parent.exists():
            return
        if record.exists() and json.loads(record.read_text()).get("cleanup", {}).get("completed"):
            return
        metadata.update(state="collecting", exit_code=exit_code)
        save_record(record, metadata)
        try:
            metadata["local_delivery_directory"] = str(collect_delivery(record, metadata))
        except Exception as error:
            metadata["delivery_error"] = str(error)
        metadata.update(state="completed" if exit_code == 0 else "failed", exit_code=exit_code)
        save_record(record, metadata)


def collect_delivery(record: Path, metadata: dict) -> Path:
    """Retrieve outputs atomically, without exposing a host directory to the worker."""
    delivery = record.parent / "delivery"
    if delivery.is_dir():
        return delivery
    staging = record.parent / f".delivery-{uuid.uuid4().hex}"
    staging.mkdir(mode=0o700)
    try:
        sbx("cp", f"{metadata['sandbox']}:{metadata['delivery_directory']}", str(staging / "delivery"))
        (staging / "delivery").rename(delivery)
    finally:
        shutil.rmtree(staging)
    return delivery


def result(task: Task) -> TaskResult:
    metadata = status(task)
    if metadata["state"] not in {"completed", "failed"}:
        raise ValueError("Task has not finished yet")
    record = REPOSITORY / "executions" / task.task_id / "task.json"
    delivery = collect_delivery(record, metadata)
    patch = delivery / "worker.patch"
    report = delivery / "delivery-report.md"
    return TaskResult(
        task_id=task.task_id,
        state=metadata["state"],
        delivery_directory=str(delivery),
        files=sorted(str(path.relative_to(delivery)) for path in delivery.rglob("*") if path.is_file()),
        patch_file=str(patch) if patch.is_file() else None,
        report_file=str(report) if report.is_file() else None,
    )


def pid_running(pid: int) -> bool:
    """Check process existence and exclude exited processes awaiting reaping."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        # Existence was confirmed above; restricted hosts may prohibit ps.
        return True
    state = result.stdout.strip()
    return result.returncode == 0 and bool(state) and not state.startswith("Z")


def status(task: Task) -> dict:
    """Return persisted execution state; never infer success from a missing PID."""
    record = REPOSITORY / "executions" / task.task_id / "task.json"
    try:
        metadata = json.loads(record.read_text())
    except FileNotFoundError:
        raise ValueError(f"Unknown task ID: {task.task_id}") from None
    if metadata.get("id") != task.task_id or metadata.get("pid") != task.pid:
        raise ValueError("Task handle does not match its saved ID and PID")
    running = False
    if metadata["state"] in {"launched", "unknown"}:
        running = pid_running(task.pid)
        if not running:
            # The watcher may have saved the exit result during the PID check.
            metadata = json.loads(record.read_text())
            if metadata["state"] in {"launched", "unknown"}:
                metadata.update(
                    state="failed",
                    error="Worker process is no longer running; its exit code is unavailable. "
                    "Inspect agent.log and the sandbox.",
                )
        else:
            metadata.update(state="launched")
    metadata["running"] = running
    return metadata


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed: {result.stderr.strip()}")
    return result.stdout


def sbx(*args: str) -> str:
    return run("sbx", "--no-input", *args)


def configure_network(name: str) -> None:
    # Reuse the notebook's actual allowlist rather than maintain a second copy.
    notebook = json.loads((REPOSITORY / "sandbox-setup.ipynb").read_text())
    source = "\n".join("".join(cell["source"]) for cell in notebook["cells"])
    match = re.search(r"```bash\n(allowed_domains=\([\s\S]*?\n\})\n```", source)
    if not match:
        raise RuntimeError("Cannot locate notebook network rules")
    script = match[1]
    # Host policy and inherited kit permissions are trusted, not audited at launch.
    run("bash", "-e", "-c", script + '\napply_network_rules "$1"', "network", name)


def executions() -> list[ExecutionSummary]:
    summaries = []
    root = REPOSITORY / "executions"
    if not root.exists():
        return summaries
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or not directory.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", directory.name):
            continue
        try:
            metadata = json.loads((directory / "task.json").read_text())
            if metadata.get("id") != directory.name:
                raise ValueError("Record ID does not match directory")
            pid = metadata.get("pid")
            running = pid_running(pid) if pid else False
            state = metadata["state"]
            if state in {"launched", "unknown"} and not running:
                state = "failed"
            summaries.append(ExecutionSummary(
                task_id=directory.name, pid=pid, state=state, running=running,
                sandbox=metadata.get("sandbox"),
                cleaned=metadata.get("cleanup", {}).get("completed", False),
                error=metadata.get("cleanup", {}).get("error") or metadata.get("error"),
            ))
        except (OSError, ValueError, KeyError, TypeError) as error:
            summaries.append(ExecutionSummary(directory.name, None, "unknown", False, None, False, str(error)))
    return summaries


def cleanup(task: Task | str, delete_artifacts: bool = False) -> CleanupResult:
    task_id = task.task_id if isinstance(task, Task) else task
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise ValueError("Invalid task ID")
    directory = REPOSITORY / "executions" / task_id
    if directory.is_symlink():
        raise ValueError("Execution directory must not be a symbolic link")
    record = directory / "task.json"
    if not record.is_file():
        raise ValueError(f"Unknown task ID: {task_id}")
    # Prevent concurrent cleanup requests from deleting resources twice.
    with (directory / ".cleanup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Cleanup is already in progress") from None
        metadata = json.loads(record.read_text())
        if metadata.get("id") != task_id:
            raise ValueError("Task ID does not match its record")
        if isinstance(task, Task) and metadata.get("pid") != task.pid:
            raise ValueError("Task handle does not match its saved ID and PID")
        if metadata["state"] in {"preparing", "collecting"} or (
            metadata.get("pid") and pid_running(metadata["pid"])
        ):
            raise ValueError("Cannot clean an active task or one collecting outputs")
        progress = metadata.setdefault("cleanup", {})
        try:
            if not progress.get("sandbox_removed"):
                sandbox = metadata.get("sandbox")
                if sandbox and sandbox != f"agent-{task_id}":
                    raise ValueError("Unexpected sandbox name in task record")
                if metadata.get("pid") and metadata.get("delivery_directory"):
                    collect_delivery(record, metadata)
                if sandbox:
                    try:
                        sbx("rm", "--force", sandbox)
                    except RuntimeError as error:
                        if not re.search(r"sandbox[^\n]*(?:not found|does not exist)|no such sandbox", str(error).lower()):
                            raise
                progress["sandbox_removed"] = True
                save_record(record, metadata)
            if not progress.get("checkout_removed"):
                worktree = directory / "worktree"
                if worktree.exists():
                    run("git", "worktree", "remove", "--force", str(worktree), cwd=REPOSITORY)
                checkout = directory / "checkout"
                if checkout.is_symlink():
                    checkout.unlink()
                elif checkout.exists():
                    shutil.rmtree(checkout)
                progress["checkout_removed"] = True
                save_record(record, metadata)
            progress.update(completed=True)
            progress.pop("error", None)
            save_record(record, metadata)
            delivery = directory / "delivery"
            local_delivery = str(delivery) if delivery.is_dir() and not delete_artifacts else None
            if delete_artifacts:
                shutil.rmtree(directory)
            return CleanupResult(task_id, True, True, delete_artifacts, local_delivery)
        except Exception as error:
            progress["error"] = str(error)
            if directory.exists():
                save_record(record, metadata)
            raise


def start(task: TaskRequest) -> Task:
    task_id = uuid.uuid4().hex
    executions = REPOSITORY / "executions"
    executions.mkdir(mode=0o700, exist_ok=True)
    directory = executions / task_id
    directory.mkdir(mode=0o700)
    name = f"agent-{task_id}"
    branch = f"agent-task/{task_id}"
    checkout = directory / "checkout"
    metadata = {"id": task_id, "sandbox": name, "branch": branch, "state": "preparing", "model": task.model}
    metadata["reasoning_effort"] = task.reasoning_effort
    record = directory / "task.json"
    save_record(record, metadata)
    created = False
    try:
        base = run("git", "rev-parse", "HEAD", cwd=REPOSITORY).strip()
        # Copy Git history without hardlinks or shared metadata. The task branch
        # exists only in the independent clone, leaving the host repository alone.
        run("git", "clone", "--no-local", "--single-branch", "--no-checkout",
            str(REPOSITORY), str(checkout))
        run("git", "checkout", "-b", branch, base, cwd=checkout)
        run("git", "remote", "remove", "origin", cwd=checkout)
        instructions = (REPOSITORY / "sub-agent.md").read_text()
        for path in list(checkout.iterdir()):
            if path.name.lower() in {"agent.md", "agents.md"}:
                path.unlink()
        (checkout / "AGENTS.md").write_text(instructions)
        run("git", "add", "-A", cwd=checkout)
        run("git", "-c", "user.name=Task setup", "-c", "user.email=setup@localhost",
            "commit", "-m", "Configure worker instructions", cwd=checkout)
        worker_base = run("git", "rev-parse", "HEAD", cwd=checkout).strip()
        sbx("create", "--name", name, "--pull", "never", "--template", TEMPLATE,
            "--skills", "off", "--static-mcp", "none", "codex")
        created = True
        configure_network(name)
        home = PurePosixPath(sbx("exec", name, "printenv", "HOME").strip())
        if not home.is_absolute():
            raise RuntimeError("Sandbox agent HOME must be an absolute path")
        sandbox_root = home / "executions" / task_id
        sandbox_checkout = str(sandbox_root / "task")
        sandbox_delivery = str(sandbox_root / "delivery")
        sandbox_prompt = str(sandbox_root / "prompt.txt")
        metadata.update(workspace=sandbox_checkout, delivery_directory=sandbox_delivery)
        (directory / "prompt.txt").write_text(
            f"{task.task}\n\nAssigned branch: {branch}\nDelivery base: {worker_base}\n"
            f"Read AGENTS.md. Write a readable worker.patch and delivery-report.md in {sandbox_delivery}.\n"
        )
        sbx("exec", name, "mkdir", "-p", sandbox_delivery)
        sbx("cp", str(checkout), f"{name}:{sandbox_checkout}")
        sbx("cp", str(directory / "prompt.txt"), f"{name}:{sandbox_prompt}")
        # Retain all output outside MCP stdout and launch asynchronously.
        worker_command = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox",
                          "--model", task.model, "-C", sandbox_checkout]
        if task.reasoning_effort is not None:
            worker_command.extend(["-c", f"model_reasoning_effort={json.dumps(task.reasoning_effort)}"])
        with (directory / "agent.log").open("wb") as log:
            process = Popen(
                ["sbx", "--no-input", "exec", "-w", sandbox_checkout, name,
                 "sh", "-c", 'prompt=$1\nshift\nexec "$@" - < "$prompt"',
                 "worker", sandbox_prompt, *worker_command],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        metadata.update(state="launched", pid=process.pid, base=base, worker_base=worker_base)
        save_record(record, metadata)
        # Reap the CLI and persist its exit status without blocking the MCP request.
        threading.Thread(
            target=watch_task, args=(process, record, metadata.copy()), daemon=True
        ).start()
        return Task(task_id=task_id, pid=process.pid)
    except Exception as error:
        metadata.update(state="failed", error=str(error))
        save_record(record, metadata)
        if created:
            try:
                sbx("stop", name)
            except Exception:
                pass
        raise RuntimeError(f"Task setup failed; diagnostics retained at {directory}: {error}") from error
