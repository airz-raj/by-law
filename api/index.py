import sys
import os

# Add the project root to the Python path so the 'app' and 'web' modules can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import create_app

app = create_app()
