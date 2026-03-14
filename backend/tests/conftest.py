"""
Pytest configuration for backend tests

This conftest.py configures the test environment:
- Adds project root to sys.path for imports from root-level modules
- Configures pytest fixtures
"""

import sys
from pathlib import Path

# Add project root to sys.path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend to sys.path
backend_root = Path(__file__).parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
