# Autonomous coding agents

This repository demonstrates autonomous coding agents running in isolated Docker sandboxes, with limited network access and Git bundles for delivering their work.

Start with [sandbox-setup.ipynb](sandbox-setup.ipynb). The notebook introduces Docker Sandboxes from scratch and walks through installation, locked-down networking, the domain allowlist, policy checks, saving a template, reuse, and cleanup. Open it in PyCharm, Jupyter, or a notebook viewer and copy the command blocks into a host Bash terminal as you read. No Python kernel is required.

The setup walkthrough prepares the environment. Git worktree transfer, task execution, and bundle retrieval will be covered separately.

See [WHITELISTED_DOMAINS.md](WHITELISTED_DOMAINS.md) for approved domains and proposed additions.
