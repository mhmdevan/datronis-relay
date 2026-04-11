# Release Checklist

From v1.0.0 onward, every release goes through this checklist. CI automates the mechanical parts; the manual section exists because some things (announcement, pre-release sanity) need a human.

## Pre-release (1-2 days before tagging)

- [ ] **All planned PRs merged** — no dangling branches that should be in this release.
- [ ] **`docs/changelog.md`** has a complete `## [Unreleased]` section with every user-visible change, grouped into Added / Changed / Deprecated / Removed / Fixed / Security.
- [ ] **Breaking changes** (if any — v1.x should have none) are documented with a migration table.
- [ ] **Deprecations** (if any) have matching `DeprecationWarning` calls in the code.
- [ ] **`docs/api_reference.md`** updated if the public surface changed.
- [ ] **`config.example.yaml`** updated if there are new optional fields.
- [ ] **Benchmarks** run fresh (`python scripts/benchmark.py`) and results pasted into `docs/performance.md`. Compare against the previous release — if p95 regressed by >20%, investigate before tagging.
- [ ] **Dependabot / renovate** PRs reviewed and merged if compatible.
- [ ] **Security advisories** checked — no open `dependabot` high/critical alerts.

## Version bump (commit before tagging)

- [ ] `pyproject.toml` → new version
- [ ] `src/datronis_relay/__init__.py` → `__version__ = "new"`
- [ ] `docs/changelog.md` → move `[Unreleased]` contents under `## [X.Y.Z] — YYYY-MM-DD`, create a fresh empty `[Unreleased]` section on top
- [ ] `README.md` → status line reflects the new version
- [ ] Dockerfile / docker-compose image tag (if hardcoded)

Commit message format: `chore(release): X.Y.Z`

## Pre-flight (run locally on the commit you're about to tag)

```bash
# everything must be green
ruff check .
ruff format --check .
mypy src
pytest -m "not integration"
pytest -m integration

# build the wheel and install it in a clean venv
python -m build
python -m venv /tmp/releasetest
/tmp/releasetest/bin/pip install dist/*.whl
/tmp/releasetest/bin/python -c "import datronis_relay; print(datronis_relay.__version__)"

# smoke-test the docs build
pip install -e ".[docs]"
mkdocs build --strict
```

## Tag + push

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

The `release.yml` workflow takes over:
- Verifies the tag matches `pyproject.toml` and `__init__.py`.
- Re-runs the full test suite.
- Builds sdist + wheel.
- Publishes to PyPI via trusted publishing.
- Creates a GitHub release with auto-generated notes + the wheel + sdist as assets.

The `docs.yml` workflow deploys the new site to GitHub Pages when `main` is pushed.

## Post-release (within 24 hours)

- [ ] **Verify the PyPI page** shows the new version and metadata.
- [ ] **`pip install datronis-relay==X.Y.Z`** on a clean machine — does `datronis-relay --version` match?
- [ ] **Docker image** (if you build one) — tag and push with both `:X.Y.Z` and `:latest`.
- [ ] **GitHub release notes** — the auto-generated notes are good enough for a patch; for minors and majors, edit the release to link the changelog section and highlight the top 3-5 changes.
- [ ] **Announcement** — pinned GitHub discussion for minors and majors. Patches don't need one.
- [ ] **Update the roadmap** — mark the completed phase items, note what landed, roll the next phase forward.

## Security release (off-cycle)

When a security fix can't wait for the next scheduled release:

1. Prepare the fix on a private branch via GitHub's security advisory flow.
2. Follow the normal version bump + tag + CI flow.
3. Bump the patch version (`1.2.3` → `1.2.4`).
4. The release notes mention a security fix without disclosing exploitation details until after the patch has been out for 7 days.
5. Credit the reporter in the release notes (unless they asked to stay anonymous).
6. If you maintain older minors for backport, cherry-pick the fix onto those branches and cut patch releases for each.

## What NOT to do during a release

- **Do not** skip the pre-flight checklist because "CI will catch it." CI catches most things, but the smoke-test install on a clean venv catches the ones that didn't fail in the source-checkout environment.
- **Do not** tag from a branch other than `main`. Release workflows and auto-generated release notes both assume `main`.
- **Do not** edit a tag after pushing. PyPI does not allow re-uploading the same version — if the tag is wrong, bump the patch version and cut a new tag.
- **Do not** force-push `main` during or after a release. Both the tag and the changelog reference commit hashes.
- **Do not** merge further PRs onto `main` while the release workflow is running — wait for it to complete. (CI's concurrency group handles it gracefully, but the human workflow is easier when one thing ships at a time.)
