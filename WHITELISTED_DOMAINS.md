# Whitelisted domains

Docker sandboxes for sub-agents should permit outbound access only to the domains explicitly enabled for their task. A domain entry does not automatically include its subdomains; add any required subdomain explicitly.

## Requested domains

| Domain | Purpose |
| --- | --- |
| `openai.com` | OpenAI website |
| `platform.openai.com` | OpenAI API documentation and platform |
| `api.openai.com` | OpenAI API |
| `chatgpt.com` and `www.chatgpt.com` | Codex subscription-based model access |
| `ab.chatgpt.com` | Explicitly approved HTTPS endpoint; its precise runtime purpose has not been established |
| `deb.debian.org` | Debian package access; whole-host access on HTTP port 80 and HTTPS port 443 |
| `dhi.io` | Package repository configured in the sandbox at `/deb/debian/main`; whole-host access on HTTP port 80 and HTTPS port 443 |
| `docs.python.org` | Python documentation |
| `www.python.org` | Official Python source archives for pre-installing Python 3.14; HTTPS port 443 |
| `nodejs.org` | Node.js documentation, official Node.js 24 binary archives, and release checksums |
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
| `production.cloudfront.docker.com` | GET and HEAD only on `/registry-v2/docker/registry/v2/blobs/sha256/**` for Docker image layers |
| `github.com`, `raw.githubusercontent.com`, `codeload.github.com`, `api.github.com` | GET and HEAD only on `/**` for repository pages, raw files, archives, and API reads |
| `developer.mozilla.org` | JavaScript and web platform documentation |
| `cdn.playwright.dev`, `playwright.download.prss.microsoft.com` | GET/HEAD over HTTPS on `/**` for Playwright's matching Chromium and browser-support archives |
| `storage.googleapis.com` | GET/HEAD over HTTPS only on `/chrome-for-testing-public/**` for Chrome for Testing archives reached by Playwright redirects; other buckets and upload methods remain excluded |

Package and image registries provide executable code. Downloads may require additional redirect or content delivery hosts; review blocked destinations before adding exceptions. GitHub permits reads on all paths at the four explicit hosts above; other GitHub subdomains, GitHub Pages, and asset hosts are not enabled. SSH remains blocked. These reads include source code and archives, not just documentation. Downloaded code can access worker files and approved network destinations; review delivered patches before integration.

Notebook chapter 5 configures browser-download permissions; chapter 6 installs Playwright, its matching Chromium binaries, and Linux dependencies into the source template. Chrome for Testing redirects to `storage.googleapis.com` are restricted to the `/chrome-for-testing-public/**` bucket path. Browser redirects to other hosts remain blocked until reviewed and explicitly approved. Browser download hosts use HTTP method rules, not whole-host access; inherited broad allows must still be inspected, including any broad Google Storage permission.

Package registries and Docker Hub use HTTP method and path rules rather than whole-host access. GET and HEAD support image reads and existence checks; normal upload and deletion methods are excluded. URLs and headers still carry data, so read methods are not a complete guarantee against data leakage. Documentation and OpenAI domains retain whole-host HTTPS access. Normal npm publishing is blocked. A POST exception permits npm audit submissions, which normally include package names and versions. This rule does not validate request bodies; legacy audit fallback endpoints remain blocked.

pip-audit uses the PyPI vulnerability service through version-specific JSON GET requests. Package names and versions appear in the requested URLs. OSV and GitHub access are not required for this mode. See [pip-audit](https://pypi.org/project/pip-audit/).

## Inherited Codex permissions

The notebook explicitly denies HTTP POST, PUT, PATCH, DELETE, OPTIONS, TRACE, and CONNECT on `github.com:443`, `raw.githubusercontent.com:443`, `codeload.github.com:443`, and `api.github.com:443`, and allows GET/HEAD on those hosts. The method denies override inherited allows for those methods while preserving approved reads. Do not add these four HTTPS hosts to the whole-host deny list: that would block GET/HEAD too. GitHub SSH is denied separately.

These method denies cover the standard non-read methods, not arbitrary extension methods or non-HTTP transports. They do not replace the requirement to remove conflicting whole-host allows before claiming a strict GET/HEAD-only policy. The notebook checks GET/HEAD and every explicitly denied method on all four hosts and stops on unexpected decisions.

Codex kits add their own allow rules. Step 5 inspects the installed kit and applies sandbox-scoped denies for unwanted inherited destinations, including unapproved GitHub hosting domains and common operating-system package mirrors. Extend that deny list to cover every unwanted resource in the actual kit; a static list cannot cover future kit changes.

A whole-host deny overrides kit allows and cannot be reopened by an HTTP allow. Conversely, a kit's broad GitHub, registry or Docker CDN allow can bypass our narrower HTTP allow rules. Conflicting broad GitHub, registry or Docker CDN permissions require a custom kit without those permissions or restrictive organization governance before the documented GitHub and registry restrictions can be relied upon. Inspect effective policy for every worker.

The PostgreSQL image pull must be tested as an actual download in each sandbox. Docker Hub may redirect layer GETs to additional CDN hosts outside the rules above; a successful registry policy probe does not establish download access. Record the blocked host, method, path and response for host review. Only the Docker image-layer CDN path listed above is approved; review any other endpoint separately. See Docker’s [allow list](https://docs.docker.com/desktop/enterprise/allow-list/).
