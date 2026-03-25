# repo-numerator

`numerator.py` rewrites commit titles so the oldest commit becomes `#1 ...`, the next
becomes `#2 ...`, and so on. Existing leading `#<number>` prefixes are replaced, while
author information and commit dates are preserved by the history rewrite.

Usage:

```bash
python numerator.py --dry-run
python numerator.py
```
