from backend.config import Settings
from backend.main import create_app

app = create_app(Settings())
