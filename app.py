#!/usr/bin/env python3

import os
import sys

from gateway.cli import run


if __name__ == "__main__":
    sys.exit(run(root_dir=os.path.dirname(os.path.abspath(__file__))))
