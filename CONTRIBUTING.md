# Contributing

1. Open an issue first (bug report or feature request templates).
2. Create a branch from `main`: `git switch -c feat/short-name`.
3. Make the change with tests. Every adaptation rule has at least one test in
   `tests/test_rules.py`; a changed rule needs a changed test.
4. Check locally before pushing:

   ```bash
   ruff format . && ruff check . && pytest --cov
   ```

5. Open a pull request. CI must be green before merging.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
`test:`, `docs:`, `ci:`, `chore:`, with an optional scope, e.g.
`feat(rules): add review rule`.

## Releases

1. Update the version in `pyproject.toml` and `src/ct_adaptive/__init__.py`.
2. Add a section to `CHANGELOG.md`.
3. Tag and push: `git tag v0.2.0 && git push origin v0.2.0`. CI builds the
   package, re-runs the simulation and publishes the GitHub Release.
