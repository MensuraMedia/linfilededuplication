"""python3 -m linfilededuplication"""
from __future__ import annotations

import sys

from linfilededuplication.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
