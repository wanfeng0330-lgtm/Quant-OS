from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"

for path in (ROOT, API_DIR):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
