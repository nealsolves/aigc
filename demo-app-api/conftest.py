import sys
from pathlib import Path

# Ensure demo-app-api/ is on sys.path so tests can import main, scenarios, gates
sys.path.insert(0, str(Path(__file__).resolve().parent))
