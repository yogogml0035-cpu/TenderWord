"""TenderWord Backend API.

FastAPI backend service for tender document generation API.
"""

import os
import sys

# Fix module import path: add parent directory of backend to sys.path
# This ensures all modules using `from backend.xxx` absolute imports can resolve correctly
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

__version__ = "1.0.0"
__author__ = "TenderWord Team"
