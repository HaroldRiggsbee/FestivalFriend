"""OCR extraction of artist names from festival lineup poster images."""

import io
import re
import time

import requests
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from classifier import MUSICBRAINZ_HEADERS, MUSICBRAINZ_SEARCH_URL

# Lazy-loaded reader (easyocr model download happens once on first use)
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# ── Noise filters ──────────────────────────────────────────────────────────

# Dates: "June 14", "14-16 July", "2025", "Fri 21st", etc.
_DATE_PATTERN = re.compile(
    r"(?i)^("
    r"\d{1,2}[/\-\.]\d{1,2}([/\-\.]\d{2,4})?|"           # 14/06, 14-16, 14.06.2025
    r"\d{1,2}\s*(st|nd|rd|th)?\s*(of\s+)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*|"  # 14th June
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*"
    r"\s+\d{1,2}\s*(st|nd|rd|th)?(\s*[\-–]\s*\d{1,2}\s*(st|nd|rd|th)?)?|"  # June 14-16
    r"(mon|tue|wed|thu|fri|sat|sun)\w*\s+\d{1,2}|"         # Friday 21
    r"\d{1,2}\s*(st|nd|rd|th)\s+(mon|tue|wed|thu|fri|sat|sun)\w*|"
    r"20\d{2}|19\d{2}"                                      # bare years
    r")$"
)

# Sentence-like text (contains sentence punctuation mid-string)
_SENTENCE_CHARS = re.compile(r"[.!?;]")
# Multiple commas suggest a sentence or address, not an artist name
_MULTI_COMMA = re.compile(r",.*,")

# Common poster noise words
_POSTER_NOISE = re.compile(
    r"(?i)^("
    r"presents?|featuring|feat\.?|ft\.?|with|and more|"
    r"tickets?|buy\s+now|on\s+sale|sold\s+out|presale|"
    r"vip|general\s+admission|early\s+bird|"
    r"main\s+stage|stage\s*\d*|tent|arena|"
    r"day\s*\d+|day\s+one|day\s+two|day\s+three|"
    r"doors?\s+open|set\s+times?|schedule|line\s*up|"
    r"sponsored\s+by|presented\s+by|powered\s+by|"
    r"follow\s+us|share|copyright|©|all\s+rights|"
    r"terms|privacy|cookie|info|www\.|\.com|"
    r"sign\s+up|subscribe|newsletter|rsvp|"
    r"more\s+(info|artists?|acts?|tba|tbc)|"
    r"free|ages?\s+\d|all\s+ages|18\+|21\+|"
    r"parking|camping|lodging|directions|map|"
    r"food|drink|merch|vendor|"
    r"fest(ival)?(\s+\d{4})?|music\s+festival|"
    r"phase\s+\d|announcement|reveal|"
    r"[a-z]+\.(com|org|net|co|io|uk)|"  # domains
    r"#\w+"  # hashtags
    r")$"
)


def _is_ocr_noise(text):
    """Return True if text looks like a date, sentence, or poster noise."""
    text = text.strip()
    if not text:
        return True

    # Too short (single char OCR artifacts)
    if len(text) < 2:
        return True

    # Contains sentence-ending punctuation (periods, exclamation, etc.)
    if _SENTENCE_CHARS.search(text):
        return True

    # Multiple commas = sentence or list, not a single artist name
    if _MULTI_COMMA.search(text):
        return True

    # Contains colon (likely a time or label like "Stage: Main")
    if ":" in text:
        return True

    # Dates
    if _DATE_PATTERN.match(text):
        return True

    # Poster noise
    if _POSTER_NOISE.match(text):
        return True

    # Mostly digits
    digit_count = sum(1 for c in text if c.isdigit())
    if digit_count > len(text) * 0.5:
        return True

    # Too many words for an artist name
    if len(text.split()) > 6:
        return True

    # Single character or just symbols
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count < 2:
        return True

    return False


# ── Image preprocessing variants ──────────────────────────────────────────

def _make_variants(img):
    """Create multiple preprocessed versions of the image for multi-pass OCR."""
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Upscale small images
    w, h = img.size
    if max(w, h) < 1500:
        scale = 1500 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    variants = []

    # Variant 1: High contrast + sharpen (good for bold text on photos)
    v1 = ImageEnhance.Contrast(img).enhance(1.8)
    v1 = ImageEnhance.Sharpness(v1).enhance(2.0)
    variants.append(v1)

    # Variant 2: Grayscale + high contrast (good for colored text)
    v2 = ImageOps.grayscale(img).convert("RGB")
    v2 = ImageEnhance.Contrast(v2).enhance(2.0)
    variants.append(v2)

    # Variant 3: Inverted grayscale (catches light text on dark backgrounds)
    v3 = ImageOps.grayscale(img)
    v3 = ImageOps.invert(v3).convert("RGB")
    v3 = ImageEnhance.Contrast(v3).enhance(1.5)
    variants.append(v3)

    return variants


# ── MusicBrainz validation ────────────────────────────────────────────────

def _validate_artist_musicbrainz(name, _retries=0):
    """Check if a name matches a real artist on MusicBrainz.

    Returns the corrected name if found (MusicBrainz may fix casing/spelling),
    or None if no match.
    """
    try:
        resp = requests.get(
            MUSICBRAINZ_SEARCH_URL,
            params={"query": f'artist:"{name}"', "limit": 3, "fmt": "json"},
            headers=MUSICBRAINZ_HEADERS,
            timeout=10,
        )
        if resp.status_code == 503 and _retries < 3:
            time.sleep(2)
            return _validate_artist_musicbrainz(name, _retries + 1)
        if resp.status_code != 200:
            return None

        artists = resp.json().get("artists", [])
        if not artists:
            return None

        # Check if any result is a close match
        name_lower = name.lower().strip()
        for artist in artists:
            mb_name = artist.get("name", "")
            score = artist.get("score", 0)
            # High confidence exact-ish match
            if score >= 90 and mb_name.lower().strip() == name_lower:
                return mb_name
            # Fuzzy: score >= 80 and names are similar length
            if score >= 80:
                if (mb_name.lower().strip() == name_lower or
                        _fuzzy_match(name_lower, mb_name.lower().strip())):
                    return mb_name

        return None
    except Exception:
        return None


def _fuzzy_match(a, b):
    """Simple fuzzy match — allows 1-2 char differences for OCR errors."""
    if abs(len(a) - len(b)) > 2:
        return False
    # Simple Levenshtein-like check: count differences
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    diffs = len(longer) - len(shorter)
    for c1, c2 in zip(shorter, longer):
        if c1 != c2:
            diffs += 1
    return diffs <= 2


# ── Main extraction ──────────────────────────────────────────────────────

def _clean_ocr_text(raw_results):
    """Filter OCR results to plausible artist names."""
    candidates = []
    for (bbox, text, conf) in raw_results:
        text = text.strip()
        if not text or conf < 0.25:
            continue

        # Strip leading/trailing symbols
        text = re.sub(r"^[•·\-\*\|>#@\s]+", "", text)
        text = re.sub(r"[•·\-\*\|<#@\s]+$", "", text)
        text = text.strip()

        if _is_ocr_noise(text):
            continue

        # Try splitting on delimiters that appear in poster text
        if " | " in text or " / " in text:
            parts = re.split(r"\s*[|/]\s*", text)
            for part in parts:
                part = part.strip()
                if part and not _is_ocr_noise(part):
                    candidates.append(part)
            continue

        candidates.append(text)

    return candidates


def _pil_to_bytes(img):
    """Convert PIL Image to bytes for easyocr."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def extract_artists_from_image(image_source, validate=True, on_progress=None):
    """Extract artist names from a lineup poster image.

    Args:
        image_source: file-like object (upload) or URL string
        validate: if True, verify names against MusicBrainz (slower but accurate)
        on_progress: callback(stage, current_name, done, total) for progress updates

    Returns:
        list of artist name strings
    """
    def _progress(stage, name="", done=0, total=0):
        if on_progress:
            on_progress(stage, name, done, total)

    # Load image
    _progress("loading")
    if isinstance(image_source, str):
        if image_source.startswith("data:"):
            # Handle base64 data URIs (e.g. data:image/jpeg;base64,...)
            import base64
            header, encoded = image_source.split(",", 1)
            img = Image.open(io.BytesIO(base64.b64decode(encoded)))
        else:
            resp = requests.get(image_source, timeout=30, headers={
                "User-Agent": "Mozilla/5.0"
            })
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
    else:
        img = Image.open(image_source)

    # Multi-pass OCR on different image variants
    _progress("ocr")
    reader = _get_reader()
    all_candidates = []
    variants = _make_variants(img)

    for i, variant in enumerate(variants):
        _progress("ocr", f"Pass {i+1}/{len(variants)}", i, len(variants))
        results = reader.readtext(
            _pil_to_bytes(variant),
            detail=1,
            paragraph=False,
        )
        all_candidates.extend(_clean_ocr_text(results))

    # Deduplicate case-insensitively
    seen = set()
    unique = []
    for name in all_candidates:
        key = name.lower().strip()
        if key not in seen and len(key) >= 2:
            seen.add(key)
            unique.append(name)

    _progress("validating", "", 0, len(unique))

    if not validate:
        return unique

    # Validate against MusicBrainz — only keep real artists
    validated = []
    for i, name in enumerate(unique):
        _progress("validating", name, i + 1, len(unique))
        corrected = _validate_artist_musicbrainz(name)
        if corrected:
            validated.append(corrected)
        # Rate limit: MusicBrainz allows ~1 req/sec
        time.sleep(1.1)

    # Final dedup on validated names
    seen = set()
    result = []
    for name in validated:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            result.append(name)

    return result
