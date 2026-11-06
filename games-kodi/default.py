"""Kodi plugin entry point. SPDX-License-Identifier: GPL-3.0-or-later"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

from apeture_library.kodi import run  # noqa: E402


if __name__ == "__main__":
    run(sys.argv)
