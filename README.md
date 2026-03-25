# repo-numerator

`numerator.py` rewrites commit titles so the oldest commit becomes `#1 ...`, the next
becomes `#2 ...`, and so on. Existing leading `#<number>` prefixes are replaced, while
author information and commit dates are preserved by the history rewrite.

The script intentionally uses the built-in `git filter-branch` command so it works
without extra Python or Git extensions in this minimal repository.

Usage:

```bash
python numerator.py --dry-run
python numerator.py
```
