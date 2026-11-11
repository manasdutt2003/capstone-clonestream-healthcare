"""Root-level copies of the workflows for the shared class repository.

GitHub only runs workflows found in the repository's top-level `.github/workflows`. When this project sits in a sub-folder of
a shared repo, the copies written to `ci/root-workflows/` are the ones to place there. They are generated from the project's
own workflows (so the two cannot drift) and only add: a path filter, a working directory, and a unique workflow name.

Run:  python -m hcls.deploy.root_workflows
"""

from __future__ import annotations

import sys

from hcls import config

NAME_CI = "Manas Capstone 3 CI"
NAME_DEPLOY = "Manas Capstone 3 Deploy"
FILES = {"ci.yml": "manas-capstone3-ci.yml", "deploy.yml": "manas-capstone3-deploy.yml"}


def _sub(text: str, old: str, new: str, count: int | None = None) -> str:
    if old not in text:
        raise ValueError(f"workflow template changed: '{old[:50]}' not found")
    return text.replace(old, new) if count is None else text.replace(old, new, count)


def render_root(text: str, kind: str, subpath: str) -> str:
    """kind is 'ci' or 'deploy'."""
    q = f'"{subpath}"'
    out = text
    if kind == "ci":
        out = _sub(out, "name: CI\n", f"name: {NAME_CI}\n", 1)
        out = _sub(
            out,
            "on:\n  pull_request:\n    branches: [main]\n  push:\n    branches: [main]\n",
            f'on:\n  pull_request:\n    branches: [main]\n    paths:\n      - "{subpath}/**"\n  push:\n    branches: [main]\n    paths:\n      - "{subpath}/**"\n',
        )
        out = _sub(
            out,
            "permissions:\n  contents: read\n",
            f"permissions:\n  contents: read\n\ndefaults:\n  run:\n    working-directory: {q}\n",
        )
        for f in (
            "outputs/gold",
            "data/clean/HCLS_cleaned.xlsx",
            "docs/01_dq_scorecard.md",
            "docs/CLEANING.md",
            "docs/stakeholder_memos",
            "coverage.xml",
        ):
            out = _sub(out, f"            {f}\n", f"            {subpath}/{f}\n")
    else:
        out = _sub(out, "name: Deploy\n", f"name: {NAME_DEPLOY}\n", 1)
        out = _sub(out, 'workflows: ["CI"]', f'workflows: ["{NAME_CI}"]')
        out = _sub(
            out,
            "permissions:\n  contents: write\n",
            f"permissions:\n  contents: write\n\ndefaults:\n  run:\n    working-directory: {q}\n",
        )
        out = _sub(out, "          path: release\n", f"          path: {subpath}/release\n")
    return _cache(out, subpath)


def _cache(text: str, subpath: str) -> str:
    return _sub(
        text,
        "          cache: pip\n",
        f'          cache: pip\n          cache-dependency-path: "{subpath}/pyproject.toml"\n',
    )


def build() -> dict[str, str]:
    root = config.project_root()
    subpath = config.load_config()["ci"]["repo_subpath"]
    out = {}
    for inner, outer in FILES.items():
        text = (root / ".github" / "workflows" / inner).read_text(encoding="utf-8")
        out[outer] = render_root(text, "ci" if inner == "ci.yml" else "deploy", subpath)
    return out


def main() -> int:
    target = config.project_root() / "ci" / "root-workflows"
    target.mkdir(parents=True, exist_ok=True)
    for name, text in build().items():
        (target / name).write_text(text, encoding="utf-8")
        print(f"wrote ci/root-workflows/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
