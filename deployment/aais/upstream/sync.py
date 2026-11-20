#!/usr/bin/env python3
"""Fetch AAIS upstream branches and prepare isolated merge candidates."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys


@dataclass(frozen=True)
class Source:
    branch: str

    def url(self, app):
        return f"https://github.com/frappe/{app}.git"


SOURCES = {
    "bench": Source("v5.x"),
    "frappe": Source("version-16"),
    "erpnext": Source("version-16"),
    "education": Source("version-16"),
    "builder": Source("develop"),
    "lms": Source("version-16"),
    "frappe-books": Source("version-16"),
    "frappe_docker": Source("main"),
    "skills": Source("main"),
}
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[4]


def git(repo, *args, allowed=(0,)):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True, check=False
    )
    if result.returncode not in allowed:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{repo.name}: git {args[0]} failed: {detail}")
    return result


def fetch(repo, app, source):
    # Fetch only the intended source branch. Keep it distinct from the fork refs.
    git(repo, "fetch", "--no-tags", source.url(app),
        f"refs/heads/{source.branch}:refs/remotes/upstream/{source.branch}")
    git(repo, "fetch", "--no-tags", "origin",
        "refs/heads/production:refs/remotes/origin/production")


def refs(repo, source):
    base = git(repo, "rev-parse", "--verify", "refs/remotes/origin/production^{commit}").stdout.strip()
    upstream = git(
        repo, "rev-parse", "--verify", f"refs/remotes/upstream/{source.branch}^{{commit}}"
    ).stdout.strip()
    git(repo, "merge-base", base, upstream)
    return base, upstream


def status(repo, app, source, base, upstream):
    ahead, behind = git(repo, "rev-list", "--left-right", "--count", f"{base}...{upstream}").stdout.split()
    dirty = bool(git(repo, "status", "--porcelain").stdout)
    print(f"{app} ({source.branch}): {ahead} fork-only / {behind} upstream-only"
          f"{' | checkout has local changes' if dirty else ''}", flush=True)
    local = git(repo, "rev-parse", "--verify", "refs/heads/production", allowed=(0, 128))
    if local.returncode == 0 and local.stdout.strip() != base:
        print("  local production differs from origin/production. The candidate uses origin/production.")
    if behind == "0":
        return False
    preview = git(repo, "merge-tree", "--write-tree", "--name-only", base, upstream, allowed=(0, 1))
    if preview.returncode == 1:
        paths = preview.stdout.splitlines()[1:]
        for path in paths[:paths.index("") if "" in paths else len(paths)]:
            print(f"  conflict: {path}")
    else:
        print("  merges without Git conflicts")
    return True


def prepare(repo, target, branch, base, upstream):
    # Reuse recorded resolutions, but keep resolved files visible for review before staging.
    git(repo, "config", "rerere.enabled", "true")
    git(repo, "config", "rerere.autoupdate", "false")
    target.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-b", branch, str(target), base)
    result = git(
        target, "-c", "merge.conflictStyle=zdiff3",
        "merge", "--no-ff", "--no-commit", upstream, allowed=(0, 1),
    )
    print(f"  worktree: {target}")
    print(f"  base:     {base}")
    print(f"  upstream: {upstream}")
    if result.returncode == 1:
        print("  Resolve and stage the conflicts in this worktree before committing.")
    else:
        print("  Review the staged merge in this worktree before committing.")
    return result.returncode == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "prepare"):
        command = commands.add_parser(name)
        command.add_argument("apps", nargs="*", metavar="APP", help="Defaults to all forks")
        if name == "status":
            command.add_argument("--fetch", action="store_true")
        else:
            command.add_argument("--round", required=True, metavar="NAME")
    args = parser.parse_args()
    apps = list(dict.fromkeys(args.apps or SOURCES))
    if unknown := set(apps) - SOURCES.keys():
        parser.error(f"unknown fork(s): {', '.join(sorted(unknown))}")
    if args.command == "prepare" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.round):
        parser.error("--round must contain only letters, numbers, underscores or hyphens")
    workspace = args.workspace.resolve()
    errors = conflicts = False
    for app in apps:
        repo, source = workspace / app, SOURCES[app]
        try:
            if not (repo / ".git").exists():
                raise RuntimeError(f"{repo} is not a Git checkout")
            if args.command == "prepare" or args.fetch:
                fetch(repo, app, source)
            base, upstream = refs(repo, source)
            needs_merge = status(repo, app, source, base, upstream)
            if args.command == "prepare" and needs_merge:
                target = workspace / ".upstream-worktrees" / args.round / app
                conflicts |= prepare(repo, target, f"sync/{args.round}", base, upstream)
        except (OSError, RuntimeError) as error:
            print(error, file=sys.stderr)
            errors = True
    return 2 if errors else int(conflicts)


if __name__ == "__main__":
    sys.exit(main())
