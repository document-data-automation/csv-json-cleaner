"""Enable ``python -m csv_json_cleaner`` straight from a clone."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
