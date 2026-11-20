# Updating the AAIS forks

Run these commands from the workspace containing the sibling app checkouts.
Git 2.38 or later is required for the merge preview, and Git 2.35 or later
supports the conflict markers used by the helper.

```bash
python3 frappe_docker/deployment/aais/upstream/sync.py status --fetch
python3 frappe_docker/deployment/aais/upstream/sync.py prepare --round 2026-11 frappe erpnext
```

The helper fetches each project's original repository and the AAIS fork's
`production` ref. `status` previews Git conflicts without changing a checkout.
`prepare` creates a branch named `sync/<round>` in each selected fork and starts
a merge in `.upstream-worktrees/<round>/<app>`. The merge is left uncommitted for
review. It starts at the fetched `origin/production` commit, so unpublished
local commits and edits such as localization work are kept in their original
checkout. If those edits should ship with the update, review and commit them
separately and include them explicitly in the candidate. `prepare` returns 1
when a candidate has conflicts, or 2 for an operational error. Already current
forks are skipped. Choose a new round name to prepare a fresh candidate.

The release lines are configured in [sync.py](sync.py). Frappe, ERPNext,
Education, LMS and Books track `version-16`. Bench tracks `v5.x`. Builder
tracks `develop`, and Docker and skills track `main`. Update Frappe and ERPNext
together when they depend on the same upstream changes.

## Reviewing the merge

Use `git status`, `git diff --cc` and `git diff --cached` inside the candidate
worktree. While the merge is pending, `HEAD` is the AAIS parent and `MERGE_HEAD`
is the exact upstream commit. For an unmerged path, Git stages 1, 2 and 3 show
the base, AAIS and upstream versions. Incorporate the relevant changes from
both sides. Git records resolutions through rerere and reuses them on later
merges. Review any reused resolution before staging it.

- Keep AAIS branding in settings, assets or hooks where supported. Move direct
  edits out of upstream files incrementally, after confirming the extension
  point produces the same result.
- Merge translations by source text and context. Preserve AAIS Bangla entries,
  add new upstream keys, check placeholders and compile the catalog. Check the
  loader's precedence when PO and CSV overlap.
- Reconcile permissions, migrations and route changes deliberately. Verify
  teacher Desk visibility, student and guardian isolation, invoice access,
  Education/LMS enrollment, and Builder pages and previews as applicable.
- Resolve source changes before rebuilding generated assets. Keep credentials,
  site exports and production data out of Git and CI.

Stage the reviewed files and commit the merge. Run the app's relevant checks
and push only the candidate branch for review. To abandon an unfinished
candidate, run `git merge --abort` inside its worktree. Remove the worktree with
`git worktree remove <path>` after it is clean and no longer needed.

## Verify the stack before promotion

Push the reviewed candidates to their AAIS forks. Once the workflow in this
repository is available on GitHub, run **Tested AAIS release** with
`verify_only=true` and pass a JSON object whose keys are app names and whose
values are the full candidate commit SHAs. Omitted apps use their current
`production` revisions. For Docker changes, dispatch against its candidate
branch after it includes this workflow. For a stack with only Docker changes,
leave the JSON object empty.

```bash
gh workflow run build-erpnext.yml --repo aais-apps/frappe_docker \
  --ref production -f verify_only=true \
  -f "candidate_revisions=$(jq -nc \
    --arg frappe "$(git -C .upstream-worktrees/2026-11/frappe rev-parse HEAD)" \
    --arg erpnext "$(git -C .upstream-worktrees/2026-11/erpnext rev-parse HEAD)" \
    '{frappe:$frappe,erpnext:$erpnext}')"
```

The run installs and migrates the combined stack on a fresh database and
uploads `release-manifest` with the exact sources. It skips registry login
and publication. For migrations affecting existing data, also test an upgrade
on an isolated restore. Review Bench, Books and skills separately, since the
combined image verification does not test changes to those forks.

Before promoting, check that each production parent still matches the tested
base or retest the updated candidates. Promote through reviewed PRs into
`production`. Coordinate dependent PRs so a partial update is safe to release,
because the existing release workflow polls the production refs. Confirm the
regular release's manifest matches the promoted commits and check the deployed
site and backup status. The current release workflow and VPS updater handle
production build, backup, migration and rollback.
