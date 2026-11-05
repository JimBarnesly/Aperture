"""Persistent library refresh service, independent of the selected skin."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))
from apeture_library.background import run_service
run_service()
