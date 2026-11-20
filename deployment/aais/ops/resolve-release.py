#!/usr/bin/env python3
"""Resolve all production inputs; the release ID changes for any app or infrastructure change."""
import hashlib
import json
import os
import pathlib
import re
import urllib.request

APP_NAMES = ("frappe", "erpnext", "education", "builder", "lms")
verify_only = os.environ.get("VERIFY_ONLY") == "true"
overrides = json.loads(os.environ.get("CANDIDATE_REVISIONS") or "{}")
if not isinstance(overrides, dict) or any(
    name not in APP_NAMES
    or not isinstance(sha, str)
    or not re.fullmatch(r"[a-f0-9]{40}", sha)
    for name, sha in overrides.items()
):
    raise SystemExit("Candidate revisions must map supported app names to full commit SHAs.")
if overrides and not verify_only:
    raise SystemExit("Candidate revisions require verify_only.")

apps = {}
for app in APP_NAMES:
    request = urllib.request.Request(
        f"https://api.github.com/repos/aais-apps/{app}/commits/{overrides.get(app, 'production')}",
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        apps[app] = json.load(response)["sha"]
    if app in overrides and apps[app] != overrides[app]:
        raise SystemExit(f"GitHub did not resolve the requested commit for {app}.")
manifest = {"apps": apps, "infrastructure": os.environ["GITHUB_SHA"]}
manifest["release_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
pathlib.Path("release.json").write_text(json.dumps(manifest, indent=2) + "\n")
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(f"release_id={manifest['release_id']}\n")
    output.write(f"publish={str(not verify_only).lower()}\n")
    for app, sha in apps.items():
        output.write(f"{app}={sha}\n")
print(json.dumps(manifest, indent=2))
