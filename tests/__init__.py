"""Test file configuration."""
import sys
from pathlib import Path

# Add the custom_components path to sys.path
repo_root = Path(__file__).parent.parent
custom_components_path = repo_root / "custom_components"
sys.path.insert(0, str(custom_components_path))
