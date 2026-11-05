"""Apply a safe initial system focus without blocking Games entry."""
import os
import sys
import xbmc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))
from apeture_library.focus import focus_initial_system
focus_initial_system(xbmc, xbmc.Monitor())
