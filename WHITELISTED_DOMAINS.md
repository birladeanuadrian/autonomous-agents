# Whitelisted domains

Docker sandboxes for sub-agents should permit outbound access only to the domains explicitly enabled for their task. A domain entry does not automatically include its subdomains; add any required subdomain explicitly.

## Requested domains

| Domain | Purpose |
| --- | --- |
| `openai.com` | OpenAI website |
| `platform.openai.com` | OpenAI API documentation and platform |
| `api.openai.com` | OpenAI API |
| `chatgpt.com` and `www.chatgpt.com` | Codex subscription-based model access |
| `docs.python.org` | Python documentation |
| `nodejs.org` | Node.js documentation |
| `dev.mysql.com` | MySQL documentation |
| `mongodb.com` | MongoDB documentation website |
| `www.mongodb.com` | MongoDB documentation |
| `postgresql.org` | PostgreSQL website and documentation |
| `www.postgresql.org` | PostgreSQL documentation |
| `docs.docker.com` | Docker documentation |

## Package registries, Docker Hub, and additional documentation

These domains are included in the notebook allowlist:

| Domain | Purpose |
| --- | --- |
| `pypi.org` | GET and HEAD on `/simple/**`; GET on `/pypi/*/*/json` for pip-audit |
| `files.pythonhosted.org` | GET and HEAD only on `/packages/**` |
| `registry.npmjs.org` | GET and HEAD on `/**`; POST only on `/-/npm/v1/security/advisories/bulk` |
| `registry-1.docker.io` | GET and HEAD only on `/v2/**` |
| `auth.docker.io` | GET and HEAD only on `/token`, with `service=registry.docker.io` |
| `developer.mozilla.org` | JavaScript and web platform documentation |

Package and image registries provide executable code. Downloads may require additional redirect or content delivery hosts; review blocked destinations before adding exceptions. GitHub remains unavailable to sub-agents.

Package registries and Docker Hub use HTTP method and path rules rather than whole-host access. GET and HEAD support image reads and existence checks; normal upload and deletion methods are excluded. URLs and headers still carry data, so read methods are not a complete guarantee against data leakage. Documentation and OpenAI domains retain whole-host HTTPS access. Normal npm publishing is blocked. A POST exception permits npm audit submissions, which normally include package names and versions. This rule does not validate request bodies; legacy audit fallback endpoints remain blocked.

pip-audit uses the PyPI vulnerability service through version-specific JSON GET requests. Package names and versions appear in the requested URLs. OSV and GitHub access are not required for this mode. See [pip-audit](https://pypi.org/project/pip-audit/).

## Inherited Codex permissions

Codex kits add their own allow rules. Step 5 inspects the installed kit and applies sandbox-scoped denies for unwanted inherited destinations, including GitHub and common operating-system package mirrors. Extend that deny list to cover every unwanted resource in the actual kit; a static list cannot cover future kit changes.

A whole-host deny overrides kit allows and cannot be reopened by an HTTP allow. Conversely, a kit's broad registry allow can bypass our narrower HTTP allow rules. Conflicting broad registry permissions require a custom kit without those permissions or restrictive organization governance before the documented registry restrictions can be relied upon. Inspect effective policy for every worker.
