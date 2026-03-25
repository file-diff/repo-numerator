import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numerator


REPO_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = REPO_ROOT / "numerator.py"


def run_git(repo_path, *args, env=None):
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def read_history(repo_path):
    output = run_git(
        repo_path,
        "log",
        "--reverse",
        "--format=%s%x00%an%x00%ae%x00%aI%x00%cI",
    )
    history = []
    for line in output.splitlines():
        subject, author_name, author_email, author_date, committer_date = line.split("\x00")
        history.append(
            {
                "subject": subject,
                "author_name": author_name,
                "author_email": author_email,
                "author_date": author_date,
                "committer_date": committer_date,
            }
        )
    return history


class NumeratorTests(unittest.TestCase):
    def test_renumber_subject_replaces_existing_prefix(self):
        self.assertEqual(numerator.renumber_subject("Initial commit", 1), "#1 Initial commit")
        self.assertEqual(numerator.renumber_subject("#99 Existing prefix", 2), "#2 Existing prefix")

    def test_script_rewrites_titles_without_changing_author_or_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            run_git(repo_path, "init")
            run_git(repo_path, "config", "user.name", "Test User")
            run_git(repo_path, "config", "user.email", "test@example.com")

            commits = [
                ("First commit", "Alice", "alice@example.com", "2024-01-01T00:00:00+00:00"),
                ("#99 Second commit", "Bob", "bob@example.com", "2024-01-02T00:00:00+00:00"),
                ("Third commit", "Carol", "carol@example.com", "2024-01-03T00:00:00+00:00"),
            ]

            for index, (subject, author_name, author_email, timestamp) in enumerate(commits, start=1):
                (repo_path / "file.txt").write_text(f"{index}\n", encoding="utf-8")
                run_git(repo_path, "add", "file.txt")
                env = os.environ.copy()
                env.update(
                    {
                        "GIT_AUTHOR_NAME": author_name,
                        "GIT_AUTHOR_EMAIL": author_email,
                        "GIT_AUTHOR_DATE": timestamp,
                        "GIT_COMMITTER_NAME": author_name,
                        "GIT_COMMITTER_EMAIL": author_email,
                        "GIT_COMMITTER_DATE": timestamp,
                    }
                )
                run_git(repo_path, "commit", "-m", subject, env=env)

            before = read_history(repo_path)

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--repo", str(repo_path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            after = read_history(repo_path)

            self.assertEqual(
                [entry["subject"] for entry in after],
                ["#1 First commit", "#2 Second commit", "#3 Third commit"],
            )
            self.assertEqual(
                [
                    (entry["author_name"], entry["author_email"], entry["author_date"], entry["committer_date"])
                    for entry in after
                ],
                [
                    (entry["author_name"], entry["author_email"], entry["author_date"], entry["committer_date"])
                    for entry in before
                ],
            )

            second_result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--repo", str(repo_path)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(
                [entry["subject"] for entry in read_history(repo_path)],
                ["#1 First commit", "#2 Second commit", "#3 Third commit"],
            )


if __name__ == "__main__":
    unittest.main()
