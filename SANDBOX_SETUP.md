# Local setup script

Run from this repository in an interactive terminal on an Apple silicon Mac:

```bash
bash sandbox-setup.sh
```

This automates the setup commands in `sandbox-setup.ipynb`, retaining interactive
Docker/OpenAI sign-ins and policy review. Homebrew must already be installed.
The notebook remains the detailed walkthrough. The script installs software
and changes local Docker Sandboxes policies; it does not implement worker-task
orchestration. Compilation and browser downloads can take several minutes.

Use `bash sandbox-setup.sh --help` for options. For example:

```bash
bash sandbox-setup.sh --sandbox my-source --template my-agent:v1 --worker my-demo --auth api-key
```

The default authentication method is OpenAI OAuth. API-key mode prompts through
`sbx secret set openai`; never put the key in command-line arguments. Both modes
configure a global host-managed credential. Docker sign-in is separate. Docker
manages token refresh; authentication errors may require signing in again.

The script detects an existing global `default-deny-all` policy and skips
initialization. If it is absent, the script asks before initializing it; continue
only on a fresh installation. The script never resets global policy. Review
every sandbox's inherited and effective permissions. Add unwanted inherited
hosts with repeated `--deny-host HOST`
options. Do not deny approved GitHub/registry hosts wholesale: host denies also
block approved reads. Conflicting broad permissions need a custom kit or
organization policy before continuing. Answer `yes` only when the review passes.

Expected denials return nonzero and are handled explicitly. Check the reported
policy decisions and confirm the three real forbidden requests in policy logs;
network errors alone do not prove blocking. Missing evidence means stop.

Existing resources are not replaced. Failures retain partial resources for
inspection; there is no automatic rollback or resume. Inspect listings and
preserve needed files before choosing fresh names or deleting partial resources.
No coding agent starts during setup. The optional interactive model check is:

```bash
bash sandbox-setup.sh model-check
```

This opens Codex in the demo worker and may consume model usage. Ask for the
authentication-only reply described by the script, then exit with `/exit`.

Destructive cleanup is a separate action with confirmation prompts:

```bash
bash sandbox-setup.sh cleanup
```

Use the same resource-name options used during setup. Both named sandboxes must
exist for this cleanup sequence; otherwise remove only the existing resources
individually using the notebook's commands. Template deletion is confirmed
separately; declining it retains the template. Cleanup does not reset policies
or delete global credentials.

Project-specific `pip-audit`, `npm audit`, and desktop/mobile application
screenshots are usage examples in the notebook. They need installed project
dependencies or a running application and are not run by template setup.

Validation uses Bash syntax checking and mocked CLI sequencing. A real full
setup still depends on Docker authentication, installed kit rules, downloads,
and the supported sandbox base image. The runtime versions and Python checksum
match the notebook; Playwright resolves the latest version at setup time and
records it in the template's package lockfile.
