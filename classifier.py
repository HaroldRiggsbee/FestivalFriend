import time

import requests

MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/artist"
MUSICBRAINZ_HEADERS = {
    "User-Agent": "FestivalFriend/1.0 (https://github.com/festivalfriend)",
    "Accept": "application/json",
}

# Map MusicBrainz tags to simplified timbre/vibe descriptors
TIMBRE_MAP = {
    "energetic": ["punk", "hardcore", "metal", "thrash", "power metal", "hard rock", "drum and bass", "gabber"],
    "chill": ["ambient", "chillout", "lo-fi", "downtempo", "trip-hop", "lounge", "new age", "easy listening"],
    "dark": ["gothic", "darkwave", "doom", "black metal", "death metal", "industrial", "dark ambient", "witch house"],
    "dreamy": ["shoegaze", "dream pop", "ethereal", "ambient pop", "slowcore", "chamber pop"],
    "groovy": ["funk", "disco", "house", "soul", "groove", "dancehall", "afrobeat", "boogie"],
    "melodic": ["pop", "singer-songwriter", "folk", "baroque pop", "power pop", "indie pop", "soft rock"],
    "heavy": ["metal", "sludge", "stoner rock", "grunge", "noise rock", "post-metal", "djent"],
    "atmospheric": ["post-rock", "ambient", "shoegaze", "space rock", "drone", "ethereal wave"],
    "raw": ["garage rock", "punk", "lo-fi", "noise", "grindcore", "crust punk", "post-punk"],
    "experimental": ["avant-garde", "experimental", "noise", "art rock", "free jazz", "musique concrète"],
    "smooth": ["r&b", "soul", "jazz", "smooth jazz", "neo soul", "quiet storm", "bossa nova"],
    "uplifting": ["trance", "euphoric", "gospel", "reggae", "ska", "happy hardcore"],
    "electronic": ["electronic", "techno", "house", "edm", "synth", "electro", "idm", "dubstep"],
    "acoustic": ["acoustic", "folk", "unplugged", "bluegrass", "country", "americana"],
}


def _search_artist(name):
    """Search MusicBrainz for an artist by name. Returns artist dict or None."""
    resp = requests.get(
        MUSICBRAINZ_SEARCH_URL,
        params={"query": f'artist:"{name}"', "limit": 1, "fmt": "json"},
        headers=MUSICBRAINZ_HEADERS,
        timeout=10,
    )
    if resp.status_code == 503:
        time.sleep(2)
        return _search_artist(name)
    resp.raise_for_status()
    artists = resp.json().get("artists", [])
    return artists[0] if artists else None


def _get_artist_tags(artist_id):
    """Get genre tags for an artist from MusicBrainz."""
    url = f"https://musicbrainz.org/ws/2/artist/{artist_id}"
    resp = requests.get(
        url,
        params={"inc": "tags", "fmt": "json"},
        headers=MUSICBRAINZ_HEADERS,
        timeout=10,
    )
    if resp.status_code == 503:
        time.sleep(2)
        return _get_artist_tags(artist_id)
    if resp.status_code != 200:
        return []
    tags = resp.json().get("tags", [])
    # Sort by count (most popular tags first) and return names
    tags.sort(key=lambda t: t.get("count", 0), reverse=True)
    return [t["name"].lower() for t in tags if t.get("count", 0) > 0]


import re as _re

# Patterns for tags that are NOT genres (nationalities, years, locations, etc.)
_NON_GENRE_PATTERN = _re.compile(
    r"^("
    r"\d{4}s?|"  # years like 2024, 1990s
    r"american|british|english|irish|scottish|welsh|australian|canadian|"
    r"french|german|italian|spanish|dutch|swedish|norwegian|danish|finnish|"
    r"japanese|korean|chinese|brazilian|mexican|colombian|argentine|"
    r"african|nigerian|south african|jamaican|cuban|puerto rican|"
    r"indian|russian|polish|belgian|austrian|swiss|portuguese|icelandic|"
    r"new zealand|"
    r"male vocalists?|female vocalists?|"
    r"seen live|favorites?|favourites?|"
    r"under \d+|spotify|"
    r"\d+s"  # decades like 80s, 90s
    r")$"
)


def _tags_to_genres(tags):
    """Extract genre labels from MusicBrainz tags, filtering out non-genres."""
    if not tags:
        return ["unknown"]
    filtered = [t for t in tags if not _NON_GENRE_PATTERN.match(t)]
    if not filtered:
        return tags[:3]
    return filtered[:3]


def _tags_to_timbre(tags):
    """Map MusicBrainz tags to timbre/vibe descriptors."""
    if not tags:
        return ["unknown"]

    descriptors = []
    tag_set = set(tags)
    for descriptor, keywords in TIMBRE_MAP.items():
        for keyword in keywords:
            if keyword in tag_set or any(keyword in t for t in tag_set):
                descriptors.append(descriptor)
                break
        if len(descriptors) >= 4:
            break

    if not descriptors:
        descriptors.append("dynamic")
    return descriptors


def classify_artist(name):
    """Classify an artist using MusicBrainz API."""
    artist = _search_artist(name)
    if not artist:
        return {"genres": ["unknown"], "timbre": ["unknown"]}

    artist_id = artist.get("id")
    if not artist_id:
        return {"genres": ["unknown"], "timbre": ["unknown"]}

    tags = _get_artist_tags(artist_id)
    genres = _tags_to_genres(tags)
    timbre = _tags_to_timbre(tags)

    return {"genres": genres, "timbre": timbre}


def classify_batch(names, existing_data, on_progress=None):
    """Classify a batch of artists using MusicBrainz API.

    - If an artist is in the DB with real genres, skip (keep existing data).
    - If an artist is in the DB as 'unknown', re-query to try to get real data.
    - If an artist is new, query MusicBrainz.
    """
    classifications = {}
    total = len(names)
    for i, name in enumerate(names, 1):
        key = name.strip().lower()
        # Skip if already classified with real (non-unknown) data
        if key in existing_data.get("artists", {}):
            existing = existing_data["artists"][key]
            if existing.get("genres") and existing["genres"] != ["unknown"]:
                if on_progress:
                    on_progress(name, i, total)
                continue
        # New artist or previously unknown — query MusicBrainz
        try:
            result = classify_artist(name)
            classifications[name] = result
        except Exception:
            classifications[name] = {"genres": ["unknown"], "timbre": ["unknown"]}
        if on_progress:
            on_progress(name, i, total)
        # MusicBrainz rate limit: 1 request/sec, we make 2 per artist
        time.sleep(1.1)
    return classifications
