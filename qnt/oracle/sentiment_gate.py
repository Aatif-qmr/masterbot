import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sentiment.reader import get_current_sentiment


def get_sentiment_score():
    """Returns the current sentiment score (-1.0 to 1.0)."""
    return get_current_sentiment().get("score", 0.0)
