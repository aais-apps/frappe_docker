#!/usr/bin/env python3
"""Resolve all production inputs; the release ID changes for any app or infrastructure change."""
import hashlib
import json
import os
import pathlib
import urllib.request

apps = {}
for app in ("frappe", "erpnext", "education", "builder"):
    request = urllib.request.Request(
        f"https://api.github.com/repos/aais-apps/{app}/commits/production",
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        apps[app] = json.load(response)["sha"]
manifest = {"apps": apps, "infrastructure": os.environ["GITHUB_SHA"]}
manifest["release_id"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:20]
pathlib.Path("release.json").write_text(json.dumps(manifest, indent=2) + "\n")
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(f"release_id={manifest['release_id']}\n")
    for app, sha in apps.items():
        output.write(f"{app}={sha}\n")
print(json.dumps(manifest, indent=2))
