from pathlib import Path
import sys
CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE))
import reader_job
import live_reader
