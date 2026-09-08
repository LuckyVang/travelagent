import os
import re
from datetime import datetime

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")


def _slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "itinerary"


def save_itinerary(title, content_markdown):
    """Write a confirmed itinerary to a markdown file under outputs/. Returns the file path."""
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{_slugify(title)}.md"
    path = os.path.join(OUTPUTS_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content_markdown)

    return {"status": "saved", "path": path}
