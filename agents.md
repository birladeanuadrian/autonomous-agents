# Repository purpose

This repository demonstrates the use of fully isolated, fully autonomous coding agents.

# Agent workflow

- Run sub-agents in Docker sandboxes with access limited to a small allowlist of domains.
- The main agent prepares an independent Git checkout for each sub-agent and copies it into that sub-agent's sandbox.
- The main agent starts each sub-agent with a specific task and waits for it to finish.
- Sub-agents operate autonomously in their assigned worktrees. They may read GitHub through approved GET/HEAD requests, including source and archives. GitHub write methods and SSH remain blocked; normal Git smart-HTTP clone/fetch requires POST and is not enabled.
- Each sub-agent delivers its work as a readable `worker.patch`. The main agent retrieves and reviews the patch before deciding whether to apply it.

# Setup documentation

- Keep `sandbox-setup.ipynb` as the guided setup walkthrough for someone starting from scratch. Explain each command and its expected outcome; avoid migration instructions for earlier notebook versions.
- Keep `WHITELISTED_DOMAINS.md` synchronized with the notebook's network rules.
- Distinguish the intended workflow from implemented functionality. The setup notebook prepares environments; the MCP server implements task launch, status checks, and delivery retrieval. Patch review and integration remain manual.

# Network enforcement

- Use the locked-down `deny-all` preset, then inspect effective policies for every sandbox. Codex kits add implicit allow rules; the preset and our explicit allow rules do not replace them.
- Explicitly deny unwanted inherited destinations, including unapproved GitHub hosting domains and system package mirrors. Review the installed kit's actual rules rather than assuming a fixed deny list is exhaustive.
- Apply policy to each worker separately. Saved templates do not include network rules.
- Use the registry methods and paths documented in `WHITELISTED_DOMAINS.md`: GET/HEAD for downloads, a POST exception for npm audit, and version-specific PyPI JSON GET requests for pip-audit.
- Narrow HTTP allows cannot constrain inherited whole-host allows. Resolve conflicting broad permissions before claiming GitHub or registry restrictions are enforced. Host denies cannot be overridden by HTTP allows.
- Verify a few representative allowed and denied operations, including actual requests inside the sandbox. Confirm denials in policy logs; a failed HTTP request alone does not prove enforcement.
- An allowed destination or GET/HEAD restriction is not a guarantee against data leakage. Audit requests disclose dependency information, and downloaded packages remain executable, potentially untrusted code.

# Credentials

- Configure Codex authentication on the host using Docker Sandboxes' credential management. Keep real credentials out of sandbox files, Git patches, and saved templates.
- Document Docker sign-in and OpenAI authentication as separate steps. Explain global versus sandbox-scoped credentials when showing setup commands.
- Docker manages OAuth token refresh on the host. Do not promise a fixed session lifetime; authentication failures may require renewed host-side sign-in.
