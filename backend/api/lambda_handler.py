"""Lambda handler for the FastAPI application."""

# Flat imports (`import auth_routes`) match local dev with cwd `backend/api`. The Lambda zip
# has `api/main.py` under `/var_task/api/`; a repo checkout has `main.py` next to this file.
import sys
from pathlib import Path

from mangum import Mangum

root = Path(__file__).resolve().parent
api_dir = root / "api"
if (api_dir / "main.py").is_file():
    app_dir = api_dir
else:
    app_dir = root
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from main import app

# Create the Lambda handler
# API Gateway passes the full path including /api/ prefix
handler = Mangum(app, lifespan="off")