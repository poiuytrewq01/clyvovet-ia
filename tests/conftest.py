import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["CLYVO_DB"] = str(Path(__file__).parent / "test.db")
os.environ["IA_MODO"] = "simulado"
os.environ["CLYVO_TESTE"] = "1"
