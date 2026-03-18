"""Configure pytest to include the project root in the Python path."""
import sys
import os

# Add the project root directory to sys.path so `from main import app` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
