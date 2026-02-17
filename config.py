import os
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "artists.json")
MAX_PAGE_CHARS = 12000
