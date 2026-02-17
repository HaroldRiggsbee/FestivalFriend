import math
import re
import threading
import uuid

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from classifier import classify_batch
from ocr import extract_artists_from_image
from scraper import extract_artists, fetch_page_text
from storage import load_data, merge_artists, save_data

app = Flask(__name__)
app.secret_key = "festival-friend-dev-key"

# Background job tracking: {job_id: {status, total, done, current_artist, ...}}
jobs = {}


def _clean_artist_names(names):
    """Split B2B names and strip parenthesized text, then deduplicate."""
    cleaned = []
    for name in names:
        # Split on B2B (case-insensitive, with or without spaces)
        parts = re.split(r'\s*[Bb]2[Bb]\s*', name)
        for part in parts:
            # Strip parenthesized text like (Sunrise Set)
            part = re.sub(r'\s*\([^)]*\)', '', part).strip()
            if part:
                cleaned.append(part)
    # Deduplicate case-insensitively, preserving order
    seen = set()
    result = []
    for name in cleaned:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            result.append(name)
    return result


def _run_classification(job_id, artist_names, festival_info):
    """Background worker that classifies artists and updates job progress."""
    job = jobs[job_id]
    data = load_data()

    def on_progress(artist_name, done_count, total_count):
        job["current_artist"] = artist_name
        job["done"] = done_count
        job["total"] = total_count

    try:
        classifications = classify_batch(artist_names, data, on_progress=on_progress)
        data = load_data()  # reload in case of concurrent changes
        data = merge_artists(data, artist_names, classifications, festival_info)
        save_data(data)
        job["artist_count"] = len(artist_names)
        job["festival_name"] = festival_info["name"]
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", festivals=data["festivals"])


@app.route("/scrape", methods=["POST"])
def scrape():
    url = request.form.get("url", "").strip()
    if not url:
        flash("Please enter a URL.", "error")
        return redirect(url_for("index"))

    try:
        festival_name, artist_names = extract_artists("", url)
    except Exception as e:
        flash(f"Failed to fetch or extract artists: {e}", "error")
        return redirect(url_for("index"))

    if not artist_names:
        flash("No artists found on that page.", "error")
        return redirect(url_for("index"))

    # Clean artist names: split B2B, strip parenthesized text
    artist_names = _clean_artist_names(artist_names)

    # Create a background job for classification
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "running",
        "phase": "classifying",
        "scan_status": "",
        "total": len(artist_names),
        "done": 0,
        "current_artist": "",
        "festival_name": festival_name,
        "artist_count": len(artist_names),
    }

    festival_info = {"name": festival_name, "url": url}
    thread = threading.Thread(
        target=_run_classification,
        args=(job_id, artist_names, festival_info),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("loading", job_id=job_id))


def _run_ocr_and_classify(job_id, image_data, festival_info):
    """Background worker: OCR → validate+classify in one pass."""
    import time
    from ocr import extract_artists_from_image, _validate_artist_musicbrainz
    from classifier import classify_artist

    job = jobs[job_id]
    try:
        # Phase 1: Quick OCR scan (no validation yet)
        job["phase"] = "scanning"
        job["scan_status"] = "Reading poster..."

        def ocr_progress(stage, name, done, total):
            if stage == "ocr":
                job["scan_status"] = f"Scanning image ({name})"

        candidates = extract_artists_from_image(
            image_data, validate=False, on_progress=ocr_progress
        )
        candidates = _clean_artist_names(candidates)

        if not candidates:
            job["status"] = "error"
            job["error"] = "No artist names found in the image."
            return

        # Phase 2: Validate + classify in one seamless loop
        job["phase"] = "classifying"
        job["scan_status"] = ""
        job["total"] = len(candidates)
        job["done"] = 0

        data = load_data()
        validated_names = []
        classifications = {}

        for i, name in enumerate(candidates):
            key = name.strip().lower()

            # Check if already in database with real data — skip MusicBrainz entirely
            if key in data.get("artists", {}):
                existing = data["artists"][key]
                if existing.get("genres") and existing["genres"] != ["unknown"]:
                    # Already have good data, just add to lineup
                    validated_names.append(existing["name"])
                    job["current_artist"] = existing["name"]
                    job["done"] = i + 1
                    job["artist_count"] = len(validated_names)
                    continue

            # Not in DB (or is unknown) — validate against MusicBrainz
            corrected = _validate_artist_musicbrainz(name)
            if not corrected:
                job["done"] = i + 1
                time.sleep(0.3)
                continue

            # It's a real artist — classify it
            validated_names.append(corrected)
            try:
                classifications[corrected] = classify_artist(corrected)
            except Exception:
                classifications[corrected] = {"genres": ["unknown"], "timbre": ["unknown"]}
            time.sleep(1.1)

            # Update progress — show the validated artist name
            job["current_artist"] = corrected
            job["done"] = i + 1
            job["artist_count"] = len(validated_names)

        if not validated_names:
            job["status"] = "error"
            job["error"] = "No recognized artists found in the image."
            return

        # Save results
        data = load_data()
        data = merge_artists(data, validated_names, classifications, festival_info)
        save_data(data)
        job["artist_count"] = len(validated_names)
        job["festival_name"] = festival_info["name"]
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/upload", methods=["POST"])
def upload_lineup():
    festival_name = request.form.get("festival_name", "").strip()
    image_url = request.form.get("image_url", "").strip()
    image_file = request.files.get("image_file")

    if not festival_name:
        flash("Please enter the festival name.", "error")
        return redirect(url_for("index"))

    if not image_url and (not image_file or image_file.filename == ""):
        flash("Please upload an image or paste an image URL.", "error")
        return redirect(url_for("index"))

    # Save uploaded file to bytes (can't pass file object to thread)
    if image_file and image_file.filename != "":
        import io
        image_data = io.BytesIO(image_file.read())
    else:
        image_data = image_url

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "running",
        "phase": "scanning",
        "scan_status": "Reading poster...",
        "total": 0,
        "done": 0,
        "current_artist": "",
        "festival_name": festival_name,
        "artist_count": 0,
    }

    festival_info = {"name": festival_name, "url": ""}
    thread = threading.Thread(
        target=_run_ocr_and_classify,
        args=(job_id, image_data, festival_info),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("loading", job_id=job_id))


@app.route("/loading/<job_id>")
def loading(job_id):
    if job_id not in jobs:
        flash("Job not found.", "error")
        return redirect(url_for("index"))
    return render_template("loading.html", job_id=job_id, job=jobs[job_id])


@app.route("/api/job/<job_id>")
def api_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    job = jobs[job_id]
    resp = {
        "status": job["status"],
        "phase": job.get("phase", "classifying"),
        "scan_status": job.get("scan_status", ""),
        "total": job["total"],
        "done": job["done"],
        "current_artist": job.get("current_artist", ""),
        "festival_name": job.get("festival_name", ""),
        "artist_count": job.get("artist_count", 0),
    }
    if "error" in job:
        resp["error"] = job["error"]
    return jsonify(resp)


@app.route("/artists")
def artists():
    data = load_data()
    artist_list = sorted(data["artists"].values(), key=lambda a: a["name"].lower())
    all_genres = sorted({g for a in artist_list for g in a.get("genres", [])})
    all_timbres = sorted({t for a in artist_list for t in a.get("timbre", [])})
    return render_template(
        "artists.html",
        artists=artist_list,
        all_genres=all_genres,
        all_timbres=all_timbres,
    )


@app.route("/festival/<name>")
def festival(name):
    data = load_data()
    # Find artists that belong to this festival
    artist_list = [
        a for a in data["artists"].values()
        if any(f["name"] == name for f in a.get("festivals", []))
    ]
    artist_list.sort(key=lambda a: a["name"].lower())
    all_genres = sorted({g for a in artist_list for g in a.get("genres", [])})
    all_timbres = sorted({t for a in artist_list for t in a.get("timbre", [])})
    return render_template(
        "festival.html",
        festival_name=name,
        artists=artist_list,
        all_genres=all_genres,
        all_timbres=all_timbres,
    )


def _find_similar_artists(target, all_artists, k=3):
    """Find k nearest neighbors using cosine similarity on genre+timbre vectors."""
    # Build vocabulary from all artists
    all_tags = set()
    for a in all_artists.values():
        all_tags.update(a.get("genres", []))
        all_tags.update(a.get("timbre", []))
    all_tags.discard("unknown")
    vocab = sorted(all_tags)
    if not vocab:
        return []
    tag_to_idx = {t: i for i, t in enumerate(vocab)}

    def to_vector(artist):
        vec = [0] * len(vocab)
        for g in artist.get("genres", []):
            if g in tag_to_idx:
                vec[tag_to_idx[g]] = 1
        for t in artist.get("timbre", []):
            if t in tag_to_idx:
                vec[tag_to_idx[t]] = 1
        return vec

    def cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    target_vec = to_vector(target)
    target_key = target["name"].lower()

    scored = []
    for key, a in all_artists.items():
        if key == target_key:
            continue
        if a.get("genres") == ["unknown"]:
            continue
        sim = cosine_sim(target_vec, to_vector(a))
        scored.append((sim, a))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:k]]


@app.route("/artist/<name>")
def artist_detail(name):
    data = load_data()
    artist = data["artists"].get(name.lower())
    if not artist:
        flash("Artist not found.", "error")
        return redirect(url_for("artists"))
    similar = _find_similar_artists(artist, data["artists"])
    return render_template("artist_detail.html", artist=artist, similar=similar)


@app.route("/api/artists")
def api_artists():
    data = load_data()
    return jsonify(list(data["artists"].values()))


if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=debug, host="0.0.0.0", port=port)
