import json
import os
import tempfile
from datetime import datetime, timezone

from config import DATA_FILE


def _empty_data():
    return {
        "artists": {},
        "festivals": [],
        "metadata": {"version": 1, "last_modified": None},
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return _empty_data()
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    data["metadata"]["last_modified"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(DATA_FILE), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except Exception:
        os.unlink(tmp_path)
        raise


def _normalize_name(name):
    return name.strip().lower()


def merge_artists(data, artist_names, classifications, festival_info):
    now = datetime.now(timezone.utc).isoformat()
    festival_entry = {
        "name": festival_info["name"],
        "url": festival_info["url"],
        "date_scraped": now,
    }

    # Check if this festival URL was already scraped
    url_exists = any(f["url"] == festival_info["url"] for f in data["festivals"])
    if not url_exists:
        data["festivals"].append({**festival_entry, "artist_count": len(artist_names)})

    for name in artist_names:
        key = _normalize_name(name)
        classification = classifications.get(name, {"genres": [], "timbre": []})

        if key in data["artists"]:
            artist = data["artists"][key]
            # Merge festival if not already listed
            existing_urls = {f["url"] for f in artist["festivals"]}
            if festival_info["url"] not in existing_urls:
                artist["festivals"].append(festival_entry)
            # Update classification if we got new data
            if classification["genres"]:
                artist["genres"] = classification["genres"]
                artist["timbre"] = classification["timbre"]
            artist["last_updated"] = now
        else:
            data["artists"][key] = {
                "name": name,
                "genres": classification.get("genres", []),
                "timbre": classification.get("timbre", []),
                "festivals": [festival_entry],
                "first_seen": now,
                "last_updated": now,
            }

    return data
