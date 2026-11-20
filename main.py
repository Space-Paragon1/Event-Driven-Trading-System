"""Run from a source checkout without installing: ``python main.py [options]``.

Once installed (``pip install -e .``), prefer ``trading-backtest`` or ``python -m trading``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from trading.cli import main

if __name__ == "__main__":
    sys.exit(main())
