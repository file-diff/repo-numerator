#!/usr/bin/env python3

"""Renumber git commit titles using the built-in git filter-branch command."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


PREFIX_RE = re.compile(r"^#\d+(?:\s+|$)")


def run_git(repo_path, args, *, input_text=None, env=None):
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def renumber_subject(subject, number):
    subject = PREFIX_RE.sub("", subject, count=1).lstrip()
    return f"#{number} {subject}" if subject else f"#{number}"


def revision_args():
    return ["--branches", "--tags"]


def list_commits(repo_path):
    shas = [
        line.strip()
        for line in run_git(repo_path, ["rev-list", "--reverse", *revision_args()]).splitlines()
        if line.strip()
    ]
    commits = []
    for index, sha in enumerate(shas, start=1):
        subject = run_git(repo_path, ["show", "-s", "--format=%s", sha]).rstrip("\n")
        commits.append({"number": index, "sha": sha, "subject": subject})
    return commits


def print_commits(commits):
    for commit in commits:
        print(f"{commit['number']}: {commit['sha']} {commit['subject']}")


def build_subject_map(commits):
    return {
        commit["sha"]: renumber_subject(commit["subject"], commit["number"])
        for commit in commits
    }


def rewrite_history(repo_path, subject_map):
    callback_code = """
import json
import os
import sys

with open(os.environ["COMMIT_SUBJECT_MAP_FILE"], "r", encoding="utf-8") as handle:
    subject_map = json.load(handle)

message = sys.stdin.read()
lines = message.splitlines(keepends=True)
if lines:
    first_line = lines[0]
    if first_line.endswith("\\r\\n"):
        newline = "\\r\\n"
        title = first_line[:-2]
    elif first_line.endswith("\\n"):
        newline = "\\n"
        title = first_line[:-1]
    else:
        newline = ""
        title = first_line
    title = subject_map.get(os.environ["GIT_COMMIT"], title)
    sys.stdout.write(title + newline + "".join(lines[1:]))
else:
    sys.stdout.write(subject_map.get(os.environ["GIT_COMMIT"], ""))
"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as mapping_file:
        json.dump(subject_map, mapping_file)
        mapping_path = mapping_file.name

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as callback_file:
        callback_file.write(callback_code)
        callback_path = callback_file.name

    env = os.environ.copy()
    env["FILTER_BRANCH_SQUELCH_WARNING"] = "1"
    env["COMMIT_SUBJECT_MAP_FILE"] = mapping_path

    try:
        run_git(
            repo_path,
            [
                "filter-branch",
                "-f",
                "--msg-filter",
                f"{sys.executable} {callback_path}",
                "--",
                *revision_args(),
            ],
            env=env,
        )
        original_refs = [
            line.strip()
            for line in run_git(
                repo_path,
                ["for-each-ref", "--format=%(refname)", "refs/original"],
            ).splitlines()
            if line.strip()
        ]
        for ref in original_refs:
            run_git(repo_path, ["update-ref", "-d", ref])
    finally:
        Path(mapping_path).unlink(missing_ok=True)
        Path(callback_path).unlink(missing_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="List commits and rewrite each title with a numbered prefix."
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the git repository to rewrite (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned commit titles without rewriting history.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_path = Path(args.repo).resolve()
    commits = list_commits(repo_path)

    if not commits:
        print("No commits found.")
        return 0

    print("Current commits:")
    print_commits(commits)

    subject_map = build_subject_map(commits)
    print("\nUpdated titles:")
    for commit in commits:
        print(f"{commit['number']}: {commit['sha']} {subject_map[commit['sha']]}")

    if args.dry_run:
        return 0

    rewrite_history(repo_path, subject_map)
    print("\nHistory rewritten successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
