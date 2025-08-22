"""Global test configuration for the Trafiklab integration tests.

Ensures the repository root is on sys.path so `custom_components` can be imported
in environments where pytest's rootdir isn't automatically added to sys.path.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path for 'custom_components' imports
REPO_ROOT = Path(__file__).resolve().parents[1]
repo_str = str(REPO_ROOT)
if repo_str not in sys.path:
    sys.path.insert(0, repo_str)
