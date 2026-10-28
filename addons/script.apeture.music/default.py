# SPDX-License-Identifier: GPL-3.0-or-later
"""Kodi entry point. No service or server is started."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))
from apeture_music.kodi import run

if __name__ == "__main__":
    run()
