import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))  # Also add clan_cli to PYTHONPATH

pytest_plugins = ["temporary_dir"]
