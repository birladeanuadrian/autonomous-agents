# Repository purpose

This repository demonstrates the use of fully isolated, fully autonomous coding agents.

# Agent workflow

- Run sub-agents in Docker sandboxes with access limited to a small allowlist of domains.
- The main agent prepares a dedicated Git worktree for each sub-agent and makes it available to that sub-agent's sandbox.
- The main agent starts each sub-agent with a specific task and waits for it to finish.
- Sub-agents operate autonomously in their assigned worktrees. They cannot access GitHub to clone repositories or push or pull commits.
- Each sub-agent delivers its work as a Git bundle. The main agent receives and reviews the bundle and integrates the work as appropriate.
