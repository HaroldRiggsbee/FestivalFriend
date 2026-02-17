import re
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup
from readability import Document as ReadabilityDocument

from config import MAX_PAGE_CHARS

# Words/patterns that indicate a line is NOT an artist name
NOISE_PATTERNS = re.compile(
    r"(?i)^("
    r"buy\s+tickets?|get\s+tickets?|sold\s+out|on\s+sale|presale|"
    r"vip|general\s+admission|early\s+bird|"
    r"main\s+stage|stage\s*\d*|tent|arena|"
    r"day\s*\d+|friday|saturday|sunday|monday|tuesday|wednesday|thursday|"
    r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|"
    r"aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?|"
    r"\d{1,2}[:/]\d{2}|\d{1,2}\s*(am|pm)|"
    r"doors?\s+open|set\s+times?|schedule|lineup|"
    r"sponsored\s+by|presented\s+by|powered\s+by|"
    r"follow\s+us|share|copyright|©|\d{4}|"
    r"terms|privacy|cookie|faq|contact|about|home|menu|"
    r"sign\s+up|subscribe|newsletter|email|"
    r"more\s+info|learn\s+more|read\s+more|see\s+more|"
    r"fest(ival)?(\s+\d{4})?|music\s+festival|"
    r"free|ages?\s+\d|all\s+ages|18\+|21\+|"
    r"parking|camping|lodging|directions|map|"
    r"food|drink|merch|vendor"
    r")$"
)

# Minimum/maximum word counts for a plausible artist name
MIN_WORDS = 1
MAX_WORDS = 6


def fetch_page_text(url):
    """Fetch a URL and return cleaned text content, preferring readable version."""
    raw_html = _fetch_raw_html(url)

    # Try Readability first for clean text
    try:
        doc = ReadabilityDocument(raw_html)
        readable_html = doc.summary()
        soup = BeautifulSoup(readable_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        if len(text) > 100:
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) > MAX_PAGE_CHARS:
                text = text[:MAX_PAGE_CHARS]
            return text
    except Exception:
        pass

    # Fall back to standard extraction
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS]
    return text


_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


def _fetch_raw_html(url):
    """Fetch a URL and return the raw HTML string."""
    resp = requests.get(url, timeout=30, headers=_HEADERS)
    resp.raise_for_status()
    return resp.text


def _fetch_soup(url):
    """Fetch a URL and return a BeautifulSoup object (before text extraction)."""
    return BeautifulSoup(_fetch_raw_html(url), "html.parser")


def _fetch_readable_soup(url):
    """Use Mozilla Readability to extract the main content as clean HTML.

    This mimics browser Reader View / ADA accessible text — strips nav, ads,
    footers, cookie banners, and JS-rendered chrome, keeping only the article
    body.  Returns (readable_soup, original_soup) so we can still extract the
    festival name from the full page.
    """
    raw_html = _fetch_raw_html(url)
    original_soup = BeautifulSoup(raw_html, "html.parser")

    try:
        doc = ReadabilityDocument(raw_html)
        readable_html = doc.summary()
        readable_soup = BeautifulSoup(readable_html, "html.parser")
        # Only trust readability if it found meaningful content
        text = readable_soup.get_text(strip=True)
        if len(text) > 100:
            return readable_soup, original_soup
    except Exception:
        pass

    # Readability didn't produce useful output — fall back to original
    return None, original_soup


def _try_google_cache(url):
    """Try fetching Google's cached text-only version of the page."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}&strip=1"
    try:
        resp = requests.get(cache_url, timeout=15, headers=_HEADERS)
        if resp.status_code == 200 and len(resp.text) > 500:
            return BeautifulSoup(resp.text, "html.parser")
    except Exception:
        pass
    return None


_GENERIC_NAMES = {"lineup", "artists", "line-up", "schedule", "tickets", "home", "festival"}


def _extract_festival_name(soup, url=""):
    """Try to get the festival name from <title>, <h1>, or URL."""
    candidates = []

    # Try <title> — split on common delimiters, collect all parts
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        parts = re.split(r"\s*[|\-–—:]\s*", title_tag.string.strip())
        candidates.extend(p.strip() for p in parts if p.strip())

    # Try <h1>
    h1 = soup.find("h1")
    if h1:
        candidates.append(h1.get_text(strip=True))

    # Try extracting from URL domain (e.g., "creamfields" from creamfields.com)
    if url:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
        # Strip www. and TLD
        domain_name = hostname.replace("www.", "").split(".")[0]
        if domain_name and len(domain_name) > 2:
            candidates.append(domain_name.replace("-", " ").title())

    # Pick the best candidate: skip generic names, prefer longer/more specific ones
    for candidate in candidates:
        if candidate.lower() not in _GENERIC_NAMES and len(candidate) > 2:
            # Strip trailing year/lineup words
            cleaned = re.sub(r"\s+(lineup|artists?|schedule|tickets?|\d{4})$", "", candidate, flags=re.I).strip()
            if cleaned and cleaned.lower() not in _GENERIC_NAMES:
                return cleaned
            if candidate.lower() not in _GENERIC_NAMES:
                return candidate

    return candidates[0] if candidates else "Unknown Festival"


def _is_plausible_artist(text):
    """Check if a string looks like it could be an artist name."""
    text = text.strip()
    if not text:
        return False
    # Too short or too long
    if len(text) < 2 or len(text) > 80:
        return False
    word_count = len(text.split())
    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        return False
    # Matches known noise
    if NOISE_PATTERNS.match(text):
        return False
    # Contains URLs or email-like patterns
    if re.search(r"https?://|www\.|@.*\.", text):
        return False
    # Mostly digits or punctuation
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars < len(text) * 0.4:
        return False
    # Very long single words that aren't artist names (likely URLs or codes)
    if word_count == 1 and len(text) > 30:
        return False
    return True


def _extract_from_list_elements(soup):
    """Extract potential artist names from list-like HTML structures."""
    candidates = []

    # Try lineup-specific selectors first
    specific_selectors = [
        ".lineup li", ".lineup a", ".lineup h2", ".lineup h3", ".lineup h4",
        "[class*='lineup'] li", "[class*='lineup'] a",
        "[class*='artist']", ".artist", ".performer",
        "[class*='performer']",
        "[class*='lineup'] h2", "[class*='lineup'] h3", "[class*='lineup'] h4",
    ]
    for selector in specific_selectors:
        for el in soup.select(selector):
            text = el.get_text(strip=True)
            if _is_plausible_artist(text):
                candidates.append(text)

    # Only fall back to generic selectors if specific ones found nothing
    if not candidates:
        for selector in ["li", "h2", "h3", "h4"]:
            for el in soup.select(selector):
                text = el.get_text(strip=True)
                if _is_plausible_artist(text):
                    candidates.append(text)

    return candidates


def _extract_from_text_lines(page_text):
    """Extract potential artist names from plain text lines."""
    candidates = []
    for line in page_text.split("\n"):
        line = line.strip()
        # Try comma-separated lists (common in lineup announcements)
        if "," in line and line.count(",") >= 2:
            parts = [p.strip() for p in line.split(",")]
            if all(_is_plausible_artist(p) for p in parts if p):
                candidates.extend(p for p in parts if p)
                continue
        # Try bullet/dot-separated lists
        if " • " in line or " · " in line:
            parts = re.split(r"\s*[•·]\s*", line)
            if all(_is_plausible_artist(p) for p in parts if p):
                candidates.extend(p for p in parts if p)
                continue
        # Individual lines
        if _is_plausible_artist(line):
            candidates.append(line)
    return candidates


def _deduplicate(names):
    """Remove duplicates while preserving order, case-insensitive."""
    seen = set()
    result = []
    for name in names:
        key = name.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(name.strip())
    return result


def _scope_to_main(soup):
    """Narrow the soup to inside <main> if it exists, to avoid nav/footer noise."""
    main_tag = soup.find("main")
    if main_tag:
        return main_tag
    # Try common content wrappers as fallback
    for selector in ["[role='main']", "#main-content", "#content", ".main-content", ".content"]:
        found = soup.select_one(selector)
        if found:
            return found
    return soup


def extract_artists(page_text, url):
    """Extract artist names from a festival lineup page using heuristic parsing.

    Always uses the original HTML scoped to <main> as the primary strategy.
    Readability results are merged in as a supplement (it's designed for articles,
    not lineup lists, so it can miss content).
    """
    raw_html = _fetch_raw_html(url)
    original_soup = BeautifulSoup(raw_html, "html.parser")
    festival_name = _extract_festival_name(original_soup, url)

    # Remove non-content tags
    for tag in original_soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    # Primary: original HTML scoped to <main>
    content_scope = _scope_to_main(original_soup)
    candidates = _extract_from_list_elements(content_scope)
    scoped_text = content_scope.get_text(separator="\n", strip=True)
    candidates.extend(_extract_from_text_lines(scoped_text))

    # Supplement: Readability may catch extra names from article-like sections
    try:
        doc = ReadabilityDocument(raw_html)
        readable_html = doc.summary()
        readable_soup = BeautifulSoup(readable_html, "html.parser")
        if len(readable_soup.get_text(strip=True)) > 100:
            candidates.extend(_extract_from_list_elements(readable_soup))
            readable_text = readable_soup.get_text(separator="\n", strip=True)
            candidates.extend(_extract_from_text_lines(readable_text))
    except Exception:
        pass

    artists = _deduplicate(candidates)
    return festival_name, artists
