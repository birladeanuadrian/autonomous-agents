#!/bin/bash
# Guided local setup from sandbox-setup.ipynb. Requires macOS / Apple silicon.
set -euo pipefail

sandbox_name=agent-template-source
template_name=autonomous-agent:v1
worker_name=agent-worker-demo
auth_method=oauth
action=setup
extra_denies=()

usage() {
  cat <<'USAGE'
Usage: bash sandbox-setup.sh [setup|cleanup|model-check] [options]
  --sandbox NAME       Source sandbox (default: agent-template-source)
  --template NAME      Saved template (default: autonomous-agent:v1)
  --worker NAME        Demo worker (default: agent-worker-demo)
  --auth oauth|api-key Host-managed global OpenAI credential (default: oauth)
  --deny-host HOST      Additional unwanted inherited host/pattern; repeatable
  -h, --help           Show help without making changes

setup (default) installs/checks sbx, signs in, configures and verifies policy,
installs notebook runtimes/browser, configures OpenAI auth, saves a template,
and verifies a demo worker. Browser sign-ins and policy review are interactive.
cleanup deletes the named source and worker, with separate confirmation for
the template. model-check opens Codex in the named worker.
No existing resources are automatically replaced. No global policy reset.
USAGE
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
confirm() {
  local answer
  printf '\n%s\nType yes to continue: ' "$*" >&2
  IFS= read -r answer || die "Interactive input ended; stopped."
  [ "$answer" = yes ] || die "Stopped without confirmation."
}
need_value() {
  [ "$#" -ge 2 ] && [ -n "$2" ] || die "Missing value for $1"
}
if [ "$#" -gt 0 ]; then
  case "$1" in setup|cleanup|model-check) action=$1; shift ;; esac
fi
while [ "$#" -gt 0 ]; do
  case "$1" in
    --sandbox) need_value "$@"; sandbox_name=$2; shift 2 ;;
    --template) need_value "$@"; template_name=$2; shift 2 ;;
    --worker) need_value "$@"; worker_name=$2; shift 2 ;;
    --auth) need_value "$@"; auth_method=$2; shift 2 ;;
    --deny-host) need_value "$@"; extra_denies+=("$2"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1 (use --help)" ;;
  esac
done
case "$auth_method" in oauth|api-key) ;; *) die "--auth must be oauth or api-key" ;; esac
# Reject option-like names and keep resource matching unambiguous.
for name in "$sandbox_name" "$worker_name" "$template_name"; do
  case "$name" in ''|[-.]*|*[!a-zA-Z0-9_./:-]*) die "Invalid resource name: $name" ;; esac
done
[ "$sandbox_name" != "$worker_name" ] || die "Source and worker names must differ."
[ -t 0 ] || die "Run in an interactive terminal; policy reviews and sign-ins require input."
trap 'printf "Setup command failed at line %s; inspect the error. Partial resources are retained.\n" "$LINENO" >&2' ERR

require_sbx() { command -v sbx >/dev/null 2>&1 || die "sbx is not installed; run setup first."; }

if [ "$action" = cleanup ]; then
  require_sbx
  sbx ls
  sbx template ls
  confirm "Delete BOTH named sandboxes: $sandbox_name and $worker_name? Internal files and scoped secrets will be lost. Only continue if both exist."
  sbx rm "$worker_name"
  sbx rm "$sandbox_name"
  printf '\nAlso permanently delete saved template %s? Type yes to delete; anything else retains it: ' "$template_name" >&2
  IFS= read -r delete_template || delete_template=no
  if [ "$delete_template" = yes ]; then
    sbx template rm "$template_name"
  else
    printf 'Retained template %s.\n' "$template_name"
  fi
  exit 0
fi
if [ "$action" = model-check ]; then
  require_sbx
  confirm "Open Codex in $worker_name? Model usage may be charged. Ask it to reply Authentication works without executing commands or modifying files; exit with /exit."
  sbx run --name "$worker_name"
  exit 0
fi

[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] ||
  die "This setup follows the notebook's macOS Apple silicon walkthrough."
if ! command -v sbx >/dev/null 2>&1; then
  command -v brew >/dev/null 2>&1 || die "Install Homebrew first."
  confirm "Trust docker/tap and install docker/tap/sbx with Homebrew?"
  brew trust docker/tap
  brew install docker/tap/sbx
fi
sbx --version
sbx login

# Inspect before initializing: existing policies must never be silently reset.
has_global_deny_all() {
  printf '%s\n' "$1" | awk '
    $1 == "default-deny-all" && $2 == "local" && $3 == "all" { found=1 }
    END { exit !found }'
}
policy_listing=$(sbx policy ls)
printf '%s\n' "$policy_listing"
if has_global_deny_all "$policy_listing"; then
  printf '\nGlobal deny-all policy is already initialized; keeping it.\n'
else
  confirm "No global default-deny-all policy was found. Initialize deny-all only if this is a fresh installation. If another global network policy exists, stop and review it first."
  if ! sbx policy init deny-all; then
    die "Could not initialize deny-all. Inspect sbx policy ls; do not reset existing policies just to rerun setup."
  fi
  policy_listing=$(sbx policy ls)
  printf '%s\n' "$policy_listing"
  has_global_deny_all "$policy_listing" ||
    die "Global default-deny-all policy was not confirmed after initialization. Stop and inspect the policy listing."
fi
confirm "Verify default-deny-all is active and inspect ALL additional global/organization rules. Stop if broader access remains unresolved."

# Listing failure is fatal. Inspect exact fields rather than substring names.
assert_absent() {
  local resource=$1 listing=$2
  if printf '%s\n' "$listing" | awk -v resource="$resource" '
    { for (i=1; i<=NF; i++) if ($i == resource) found=1 }
    END { exit !found }'; then
    die "Resource $resource already exists. Choose another name or use explicit cleanup."
  fi
}
sandbox_listing=$(sbx ls)
template_listing=$(sbx template ls)
printf '%s\n%s\n' "$sandbox_listing" "$template_listing"
assert_absent "$sandbox_name" "$sandbox_listing"
assert_absent "$worker_name" "$sandbox_listing"
assert_absent "$template_name" "$template_listing"

allowed_domains=(
  openai.com
  platform.openai.com
  api.openai.com
  chatgpt.com
  www.chatgpt.com
  ab.chatgpt.com
  docs.python.org
  www.python.org
  nodejs.org
  dev.mysql.com
  mongodb.com
  www.mongodb.com
  postgresql.org
  www.postgresql.org
  docs.docker.com
  developer.mozilla.org
)

# Extend this list using the installed kit's resource listing above.
denied_domains=(
  githubassets.com
  '*.githubassets.com'
  github.io
  '*.github.io'
  archive.ubuntu.com
  '*.archive.ubuntu.com'
  security.ubuntu.com
  ports.ubuntu.com
  esm.ubuntu.com
  changelogs.ubuntu.com
  keyserver.ubuntu.com
  security.debian.org
  download.docker.com
)

apply_network_rules() {
  local target_sandbox="$1"
  for domain in "${denied_domains[@]}"; do
    sbx policy deny network --sandbox "$target_sandbox" "$domain"
  done
  # Keep GitHub SSH blocked while allowing inspected HTTPS reads.
  sbx policy deny network --sandbox "$target_sandbox" github.com:22
  sbx policy deny network --sandbox "$target_sandbox" ssh.github.com
  for domain in "${allowed_domains[@]}"; do
    sbx policy allow network --sandbox "$target_sandbox" "$domain:443"
  done

  # Package sources may use HTTP or HTTPS.
  for domain in deb.debian.org dhi.io; do
    sbx policy allow network --sandbox "$target_sandbox" "$domain:80"
    sbx policy allow network --sandbox "$target_sandbox" "$domain:443"
  done

  # Use HTTP denies, never a whole-host deny, on approved GitHub HTTPS hosts.
  # Whole-host denies would block GET/HEAD as well.
  for domain in github.com raw.githubusercontent.com codeload.github.com api.github.com; do
    sbx policy deny network --sandbox "$target_sandbox" "$domain:443" --method POST,PUT,PATCH,DELETE,OPTIONS,TRACE,CONNECT --path '/**'
    sbx policy allow network --sandbox "$target_sandbox" "$domain:443" --method GET,HEAD --path '/**'
  done

  sbx policy allow network --sandbox "$target_sandbox" pypi.org:443 --method GET,HEAD --path '/simple/**'
  sbx policy allow network --sandbox "$target_sandbox" pypi.org:443 --method GET --path '/pypi/*/*/json'
  sbx policy allow network --sandbox "$target_sandbox" files.pythonhosted.org:443 --method GET,HEAD --path '/packages/**'
  sbx policy allow network --sandbox "$target_sandbox" registry.npmjs.org:443 --method GET,HEAD --path '/**'
  sbx policy allow network --sandbox "$target_sandbox" registry.npmjs.org:443 --method POST --path '/-/npm/v1/security/advisories/bulk'

  # Playwright's browser installer uses these HTTPS download mirrors.
  for domain in cdn.playwright.dev playwright.download.prss.microsoft.com; do
    sbx policy allow network --sandbox "$target_sandbox" "$domain:443" --method GET,HEAD --path '/**'
  done
  # Chrome for Testing redirects stay restricted to its public bucket.
  sbx policy allow network --sandbox "$target_sandbox" storage.googleapis.com:443 --method GET,HEAD --path '/chrome-for-testing-public/**'

  sbx policy allow network --sandbox "$target_sandbox" registry-1.docker.io:443 --method GET,HEAD --path '/v2/**'
  sbx policy allow network --sandbox "$target_sandbox" auth.docker.io:443 --method GET,HEAD --path '/token' --query 'service=registry.docker.io'
}

if [ "${#extra_denies[@]}" -gt 0 ]; then
  denied_domains+=("${extra_denies[@]}")
fi

inspect_and_apply_policy() {
  local target=$1
  sbx policy ls "$target" --source kit --decision allow --wide
  confirm "Review $target inherited kit permissions against WHITELISTED_DOMAINS.md. Every unwanted host must be in the deny list (extend with --deny-host). Conflicting broad GitHub/registry/browser-host permissions require a custom kit or organization policy; narrow allows cannot constrain them. Stop if unresolved."
  apply_network_rules "$target"
  sbx policy ls "$target" --wide
  confirm "Review the COMPLETE effective policy for $target. Confirm no unapproved inherited/global permissions or conflicting broad allows remain. Spot checks alone do not establish this."
}

expect_allowed() { "$@" || die "Expected allowed operation failed: $*"; }
expect_denied() {
  if "$@"; then die "Expected denial was ALLOWED: $*"; fi
  # A nonzero CLI status is not itself proof of a policy denial.
  printf 'Nonzero result observed; verify its denial reason in output/logs.\n'
}
check_http() {
  local target=$1 decision=$2 method=$3 url=$4
  "expect_$decision" sbx policy check http --sandbox "$target" --method "$method" "$url"
}
verify_policy() {
  local target=$1 domain method url
  for domain in github.com raw.githubusercontent.com codeload.github.com api.github.com; do
    for method in GET HEAD; do check_http "$target" allowed "$method" "https://$domain/"; done
    for method in POST PUT PATCH DELETE OPTIONS TRACE CONNECT; do
      check_http "$target" denied "$method" "https://$domain/"
    done
  done
  for domain in api.openai.com:443 docs.python.org:443; do
    expect_allowed sbx policy check network --sandbox "$target" "$domain"
  done
  for domain in github.com:22 example.com:443; do
    expect_denied sbx policy check network --sandbox "$target" "$domain"
  done
  for url in https://ab.chatgpt.com/ \
    http://deb.debian.org/debian/dists/stable/InRelease \
    https://deb.debian.org/debian/dists/stable/InRelease \
    http://dhi.io/deb/debian/main/dists/trixie/InRelease \
    https://dhi.io/deb/debian/main/dists/trixie/InRelease \
    https://cdn.playwright.dev/ https://pypi.org/simple/requests/; do
    check_http "$target" allowed GET "$url"
  done
  check_http "$target" allowed HEAD https://playwright.download.prss.microsoft.com/dbazure/download/playwright/
  for method in GET HEAD; do
    check_http "$target" allowed "$method" https://storage.googleapis.com/chrome-for-testing-public/158.0.8127.18/linux-arm64/chrome-linux-arm64.zip
  done
  check_http "$target" denied POST https://storage.googleapis.com/chrome-for-testing-public/158.0.8127.18/linux-arm64/chrome-linux-arm64.zip
  check_http "$target" denied GET https://storage.googleapis.com/unapproved-bucket/policy-probe
  check_http "$target" allowed POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk
  check_http "$target" allowed HEAD https://registry-1.docker.io/v2/library/ubuntu/manifests/latest
  check_http "$target" denied POST https://cdn.playwright.dev/
  check_http "$target" denied POST https://registry-1.docker.io/v2/library/ubuntu/blobs/uploads/
  check_http "$target" denied GET https://pypi.org/pypi/requests/json
  check_http "$target" denied POST https://pypi.org/simple/requests/
  confirm "Confirm each nonzero policy check above explicitly reported DENIED, rather than a CLI/service error."
}

verify_requests() {
  local target=$1
  expect_allowed sbx exec "$target" curl --silent --show-error --fail --max-time 15 --output /dev/null --write-out 'HTTP %{http_code}\n' https://pypi.org/simple/requests/
  expect_allowed sbx exec "$target" curl --silent --show-error --fail --max-time 15 --output /dev/null --write-out 'HTTP %{http_code}\n' https://github.com/python/cpython/blob/main/README.rst
  expect_allowed sbx exec "$target" curl --head --silent --show-error --fail --max-time 15 https://raw.githubusercontent.com/python/cpython/main/README.rst
  expect_denied sbx exec "$target" curl --include --silent --show-error --fail-with-body --max-time 15 --request POST https://github.com/
  expect_denied sbx exec "$target" curl --include --silent --show-error --fail-with-body --max-time 15 https://pypi.org/pypi/requests/json
  expect_denied sbx exec "$target" curl --include --silent --show-error --fail-with-body --max-time 15 --request POST https://pypi.org/simple/requests/
  sbx policy log "$target" --limit 20
  confirm "Confirm the policy logs for $target contain BLOCKED decisions for ALL THREE forbidden curl probes just run. Timeouts, DNS errors, upstream 404/405, and curl failures alone are insufficient. Stop if missing."
}

sbx create --name "$sandbox_name" --skills off --static-mcp none codex
inspect_and_apply_policy "$sandbox_name"
verify_policy "$sandbox_name"
verify_requests "$sandbox_name"

IFS= read -r -d '' runtime_setup <<'SANDBOX_RUNTIME_SETUP' || true
set -euo pipefail
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ca-certificates curl xz-utils build-essential pkg-config \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libffi-dev liblzma-dev libexpat1-dev libzstd-dev uuid-dev tk-dev

runtime_dir=$(mktemp -d /tmp/agent-runtimes.XXXXXX)
# sudo make altinstall can leave root-owned caches in the source tree.
cleanup_runtime() {
  local status=$?
  trap - EXIT
  if ! sudo -n rm -rf -- "$runtime_dir"; then
    printf 'Could not remove runtime build directory: %s\n' "$runtime_dir" >&2
    if [ "$status" -eq 0 ]; then status=1; fi
  fi
  exit "$status"
}
trap cleanup_runtime EXIT
cd "$runtime_dir"

case "$(uname -m)" in
  aarch64|arm64) node_arch=arm64 ;;
  x86_64|amd64) node_arch=x64 ;;
  *) echo "Unsupported Node architecture" >&2; exit 1 ;;
esac
node_version=24.22.2
node_archive="node-v$node_version-linux-$node_arch.tar.xz"
curl --fail --show-error --silent --location \
  "https://nodejs.org/dist/v$node_version/SHASUMS256.txt" -o SHASUMS256.txt
curl --fail --show-error --silent --location \
  "https://nodejs.org/dist/v$node_version/$node_archive" -o "$node_archive"
awk -v file="$node_archive" '$2 == file { print; found=1 } END { if (!found) exit 1 }' \
  SHASUMS256.txt > node.sha256
sha256sum --check node.sha256
sudo mkdir -p /opt/mini-jira-node-24
sudo tar -xJf "$node_archive" --strip-components=1 -C /opt/mini-jira-node-24
for tool in node npm npx; do
  sudo ln -sfn "/opt/mini-jira-node-24/bin/$tool" "/usr/local/bin/$tool"
done

python_version=3.14.10
python_sha256=de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032
python_archive="Python-$python_version.tar.xz"
curl --fail --show-error --silent --location \
  "https://www.python.org/ftp/python/$python_version/$python_archive" -o "$python_archive"
printf '%s  %s\n' "$python_sha256" "$python_archive" > python.sha256
sha256sum --check python.sha256
tar -xJf "$python_archive"
cd "Python-$python_version"
./configure --prefix=/opt/mini-jira-python-3.14 --with-ensurepip=install
make -j2
sudo make altinstall
sudo ln -sfn /opt/mini-jira-python-3.14/bin/python3.14 /usr/local/bin/python3.14
sudo ln -sfn /opt/mini-jira-python-3.14/bin/python3.14 /usr/local/bin/python3
sudo ln -sfn /opt/mini-jira-python-3.14/bin/python3.14 /usr/local/bin/python

# Install tools with this Python, using the approved PyPI endpoints.
sudo /opt/mini-jira-python-3.14/bin/python3.14 -m pip install \
  --index-url https://pypi.org/simple uv pip-audit
sudo ln -sfn /opt/mini-jira-python-3.14/bin/uv /usr/local/bin/uv
sudo ln -sfn /opt/mini-jira-python-3.14/bin/uvx /usr/local/bin/uvx

node --version
npm --version
python3.14 --version
python3.14 -c 'import sys, ssl, sqlite3, bz2, lzma, ctypes, compression.zstd; assert sys.version_info[:2] == (3, 14)'
node -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
python3.14 -m venv "$runtime_dir/venv-check"
"$runtime_dir/venv-check/bin/python" -m pip --version
uv --version
python3.14 -m pip_audit --version
SANDBOX_RUNTIME_SETUP
sbx exec "$sandbox_name" bash -c "$runtime_setup"
unset runtime_setup

sbx exec "$sandbox_name" sh -c 'command -v node npm python3.14 uv && node --version && python3.14 --version'

IFS= read -r -d '' browser_setup <<'SANDBOX_BROWSER_SETUP' || true
set -euo pipefail
sudo install -d -o "$(id -u)" -g "$(id -g)" /opt/mini-jira-browser
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --prefix /opt/mini-jira-browser --save-exact --registry=https://registry.npmjs.org playwright@latest

# Root privileges are only needed to install Linux system packages.
sudo /usr/local/bin/node /opt/mini-jira-browser/node_modules/playwright/cli.js install-deps chromium

# Download the browser as the worker user, into a persistent shared location.
PLAYWRIGHT_BROWSERS_PATH=/opt/mini-jira-browser/browsers /usr/local/bin/node /opt/mini-jira-browser/node_modules/playwright/cli.js install chromium

# Expose the CLI and set its browser-cache location for every invocation.
cat > /opt/mini-jira-browser/playwright <<'PLAYWRIGHT_WRAPPER'
#!/bin/sh
export PLAYWRIGHT_BROWSERS_PATH=/opt/mini-jira-browser/browsers
exec /usr/local/bin/node /opt/mini-jira-browser/node_modules/playwright/cli.js "$@"
PLAYWRIGHT_WRAPPER
chmod +x /opt/mini-jira-browser/playwright
sudo ln -sfn /opt/mini-jira-browser/playwright /usr/local/bin/playwright

# Keep a self-contained launch and screenshot check in the template.
cat > /opt/mini-jira-browser/smoke.cjs <<'BROWSER_SMOKE'
process.env.PLAYWRIGHT_BROWSERS_PATH = '/opt/mini-jira-browser/browsers';
const { chromium } = require('/opt/mini-jira-browser/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.setContent('<!doctype html><html lang="en"><title>Browser check</title><body><h1>Browser ready</h1></body></html>');
    await page.getByRole('heading', { name: 'Browser ready' }).waitFor();
    await page.screenshot({ path: process.argv[2] || '/tmp/browser-smoke.png', fullPage: true });
    console.log('Chromium launched and screenshot captured.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
BROWSER_SMOKE

playwright --version
npm --prefix /opt/mini-jira-browser ls playwright
node /opt/mini-jira-browser/smoke.cjs /tmp/browser-smoke.png
test -s /tmp/browser-smoke.png
SANDBOX_BROWSER_SETUP
sbx exec "$sandbox_name" bash -c "$browser_setup"
unset browser_setup


# Global host credential: do not embed credentials in sandbox files or templates.
case "$auth_method" in
  oauth) sbx secret set openai --oauth ;;
  api-key) sbx secret set openai ;;
esac
sbx secret ls

# Stop here if either runtime is missing or has the wrong major/minor version.
sbx exec "$sandbox_name" node -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
sbx exec "$sandbox_name" python3.14 -c 'import sys; assert sys.version_info[:2] == (3, 14)'
sbx exec "$sandbox_name" playwright --version
sbx exec "$sandbox_name" node /opt/mini-jira-browser/smoke.cjs /tmp/browser-before-save.png
sbx template save "$sandbox_name" "$template_name"
sbx template ls

sbx create --name "$worker_name" --pull never --template "$template_name" --skills off --static-mcp none codex
inspect_and_apply_policy "$worker_name"
verify_policy "$worker_name"
verify_requests "$worker_name"
sbx exec "$worker_name" node --version
sbx exec "$worker_name" npm --version
sbx exec "$worker_name" python3.14 --version
sbx exec "$worker_name" uv --version
sbx exec "$worker_name" playwright --version
sbx exec "$worker_name" node -e 'if (process.versions.node.split(".")[0] !== "24") process.exit(1)'
sbx exec "$worker_name" python3.14 -c 'import sys; assert sys.version_info[:2] == (3, 14)'
sbx exec "$worker_name" node /opt/mini-jira-browser/smoke.cjs /tmp/worker-browser-smoke.png
printf '\nSetup complete. Template: %s; demo worker: %s\n' "$template_name" "$worker_name"
printf 'No coding agent started. Use model-check for optional authentication verification.\n'
