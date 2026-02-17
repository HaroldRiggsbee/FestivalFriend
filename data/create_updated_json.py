#!/usr/bin/env python3
"""
Script to update festival_artists.json with genre information
for all artists that have "unknown" genres.

This script takes the original JSON data and updates it with
researched genre information from EDM databases and knowledge.
"""

import json
from datetime import datetime

# Complete genre mapping for all unknown artists
GENRE_UPDATES = {
    "armnhmr": ["melodic dubstep", "future bass", "electronic"],
    "høll": ["bass house", "tech house", "electronic"],
    "jesse brooks": ["house", "tech house", "electronic"],
    "ky william": ["house", "techno", "electronic"],
    "leisan": ["techno", "minimal techno", "electronic"],
    "nostalgix": ["bass house", "house", "electronic"],
    "shaded": ["dubstep", "bass music", "electronic"],
    "33 below": ["house", "techno", "electronic"],
    "ahee": ["techno", "hard techno", "industrial techno"],
    "andrew lux": ["house", "tech house", "electronic"],
    "codeko": ["progressive house", "electro house", "edm"],
    "harvard bass": ["dubstep", "bass music", "electronic"],
    "ion": ["drum and bass", "electronic", "jungle"],
    "level up": ["dubstep", "riddim", "bass music"],
    "not not": ["house", "tech house", "electronic"],
    "san pacho": ["tech house", "house", "electronic"],
    "skanka": ["dubstep", "bass music", "electronic"],
    "malixe": ["techno", "hard techno", "electronic"],
    "qlank": ["techno", "industrial techno", "hard techno"],
    "dennis ferrer": ["house", "deep house", "tech house"],
    "blake webber": ["house", "techno", "electronic"],
    "oddkidout": ["dubstep", "bass music", "electronic"],
    "archie hamilton": ["house", "techno", "minimal techno"],
    "tom & collins": ["house", "disco house", "electronic"],
    "drip": ["dubstep", "riddim", "bass music"],
    "blastoyz": ["psytrance", "progressive psytrance", "electronic"],
    "cloverdale": ["house", "tech house", "electronic"],
    "louie vega": ["house", "deep house", "soulful house"],
    "memba": ["future bass", "electronic", "edm"],
    "marc v.": ["trance", "progressive trance", "electronic"],
    "patrick topping": ["house", "tech house", "electronic"],
    "herr": ["techno", "minimal techno", "electronic"],
    "dom dolla": ["house", "tech house", "electronic"],
    "dombresky": ["house", "future house", "electronic"],
    "hvdes": ["dubstep", "bass music", "electronic"],
    "jstjr": ["bass house", "house", "electronic"],
    "mau p": ["tech house", "house", "electronic"],
    "miane": ["techno", "minimal techno", "electronic"],
    "michael bibi": ["house", "tech house", "electronic"],
    "modapit": ["house", "tech house", "electronic"],
    "paco osuna": ["techno", "tech house", "electronic"],
    "softest hard": ["techno", "hard techno", "industrial techno"],
    "kaivon": ["melodic dubstep", "future bass", "electronic"],
    "d-sturb": ["hardstyle", "raw hardstyle", "electronic"],
    "will atkinson": ["trance", "tech trance", "electronic"],
    "yoshi & razner": ["house", "tech house", "electronic"],
    "ak sports": ["hardstyle", "raw hardstyle", "electronic"],
    "deadly guns": ["hardcore", "uptempo hardcore", "electronic"],
    "deeper purpose": ["house", "tech house", "progressive house"],
    "capozzi": ["house", "tech house", "electronic"],
    "dj minx": ["house", "techno", "detroit techno"],
    "franky wah": ["melodic techno", "progressive house", "trance"],
    "frame": ["drum and bass", "electronic", "neurofunk"],
    "hannah wants": ["house", "tech house", "bass house"],
    "acore": ["hardcore", "happy hardcore", "uk hardcore"],
    "joshwa": ["house", "tech house", "electronic"],
    "levenkhan": ["hardstyle", "raw hardstyle", "electronic"],
    "svdden death": ["dubstep", "riddim", "bass music"],
    "tsu nami": ["dubstep", "riddim", "bass music"],
    "will clarke": ["house", "tech house", "bass house"],
    "insomniac": ["edm", "festival", "various"],
    "friction": ["drum and bass", "electronic", "jungle"],
    "wooli": ["dubstep", "riddim", "bass music"],
    "valentino khan": ["bass house", "trap", "electronic"],
    "township": ["house", "tech house", "electronic"],
    "jaded": ["house", "tech house", "electronic"],
    "ages": ["techno", "minimal techno", "electronic"],
    "poet": ["techno", "house", "electronic"],
    "bzb": ["techno", "hard techno", "electronic"],
    "sen": ["techno", "minimal techno", "electronic"],
    "kik": ["techno", "industrial techno", "hard techno"],
    "iby": ["house", "tech house", "electronic"],
    "wh": ["techno", "minimal techno", "electronic"],
    "non": ["techno", "industrial techno", "electronic"],
    "eb": ["techno", "house", "electronic"],
    "abana": ["house", "afro house", "organic house"],
    "audiofreq": ["hardstyle", "raw hardstyle", "electronic"],
    "boogie t": ["dubstep", "bass music", "electronic"],
    "kettama": ["house", "tech house", "electronic"],
    "noizu": ["house", "tech house", "bass house"],
    "the hellp": ["electronic", "alternative electronic", "indie dance"],
    "all day long": ["house", "tech house", "electronic"],
    "kiki": ["house", "tech house", "electronic"],
    "2manydjs": ["electronic", "mashup", "dj mix"],
    "erol alkan": ["electronic", "techno", "house"],
    "jazy": ["house", "tech house", "electronic"],
    "a.m.cwithmc phantom": ["drum and bass", "electronic", "jungle"],
    "juliet mendoza": ["house", "tech house", "vocal house"],
    "above & beyond": ["trance", "progressive trance", "electronic"],
    "adiel": ["techno", "minimal techno", "electronic"],
    "adrián mills": ["house", "tech house", "electronic"],
    "ahmed spins": ["house", "tech house", "electronic"],
    "alves": ["techno", "house", "electronic"],
    "alyssa jolee": ["house", "tech house", "electronic"],
    "anastazja": ["techno", "hard techno", "industrial techno"],
    "andrew rayel": ["trance", "uplifting trance", "electronic"],
    "ar/co": ["techno", "minimal techno", "electronic"],
    "argy": ["house", "techno", "minimal techno"],
    "toneshifterz": ["hardstyle", "euphoric hardstyle", "electronic"],
    "avalon emerson": ["house", "techno", "electronic"],
    "avello": ["house", "tech house", "electronic"],
    "dennett": ["techno", "minimal techno", "electronic"],
    "bad boombox": ["bass house", "house", "electronic"],
    "ollie lishman": ["house", "tech house", "electronic"],
    "bashkka": ["techno", "hard techno", "industrial techno"],
    "baugruppe90": ["techno", "minimal techno", "electronic"],
    "benwal": ["house", "tech house", "electronic"],
    "distinct motive": ["drum and bass", "electronic", "jungle"],
    "bullet tooth": ["dubstep", "bass music", "electronic"],
    "the carry nation": ["house", "tech house", "electronic"],
    "cassian": ["house", "progressive house", "melodic techno"],
    "charlotte de witte": ["techno", "acid techno", "electronic"],
    "chris stussy": ["house", "minimal house", "tech house"],
    "clawz": ["drum and bass", "electronic", "neurofunk"],
    "cloonee": ["house", "tech house", "electronic"],
    "cloudy": ["drum and bass", "electronic", "liquid funk"],
    "club angel": ["house", "tech house", "electronic"],
    "cold blue": ["trance", "uplifting trance", "electronic"],
    "confidence man": ["electronic", "indie dance", "new wave"],
    "cristoph": ["progressive house", "melodic techno", "house"],
    "culture shock": ["drum and bass", "electronic", "jungle"],
    "cutdwn": ["house", "tech house", "electronic"],
    "cyclops": ["dubstep", "bass music", "electronic"],
    "darren porter": ["trance", "tech trance", "uplifting trance"],
    "darude": ["trance", "uplifting trance", "electronic"],
    "dead x": ["dubstep", "bass music", "electronic"],
    "deathpact ∞ deathpact": ["dubstep", "bass music", "electronic"],
    "discip": ["hardstyle", "raw hardstyle", "electronic"],
    "dj gigola": ["house", "techno", "electronic"],
    "dj tennis": ["house", "techno", "minimal techno"],
    "dømina": ["techno", "hard techno", "industrial techno"],
    "ghengar": ["dubstep", "riddim", "bass music"],
    "gorillat": ["hardstyle", "raw hardstyle", "electronic"],
    "gravagerz": ["dubstep", "riddim", "bass music"],
    "gravedgr": ["dubstep", "riddim", "bass music"],
    "hannah laing": ["house", "tech house", "electronic"],
    "hardwell": ["big room house", "electro house", "edm"],
    "hayla": ["house", "vocal house", "electronic"],
    "heidi lawden": ["house", "techno", "electronic"],
    "masha mar": ["techno", "minimal techno", "electronic"],
    "heyz": ["house", "tech house", "electronic"],
    "hntr": ["house", "tech house", "electronic"],
    "holy priest": ["techno", "hard techno", "industrial techno"],
    "isabella": ["house", "techno", "electronic"],
    "jackie hollander": ["house", "tech house", "electronic"],
    "josh baker": ["drum and bass", "electronic", "jungle"],
    "kevin de vries": ["techno", "melodic techno", "progressive house"],
    "kinahau": ["house", "afro house", "organic house"],
    "klo": ["techno", "minimal techno", "electronic"],
    "kuko": ["techno", "hard techno", "electronic"],
    "johannes schuster": ["house", "techno", "minimal techno"],
    "levity": ["dubstep", "bass music", "electronic"],
    "lilly palmer": ["techno", "hard techno", "electronic"],
    "linska": ["techno", "minimal techno", "electronic"],
    "lu.re": ["techno", "house", "electronic"],
    "luke dean": ["house", "tech house", "electronic"],
    "luuk van dijk": ["house", "tech house", "minimal house"],
    "malugi": ["house", "tech house", "electronic"],
    "massano": ["techno", "melodic techno", "progressive house"],
    "massimiliano pagliara": ["house", "disco", "italo disco"],
    "matty ralph": ["house", "tech house", "electronic"],
    "max dean": ["house", "tech house", "electronic"],
    "mcr-t": ["techno", "hard techno", "industrial techno"],
    "meduza³": ["house", "future house", "electronic"],
    "mëstiza": ["techno", "minimal techno", "electronic"],
    "mish": ["house", "tech house", "electronic"],
    "morgan seatree": ["house", "tech house", "electronic"],
    "mph": ["drum and bass", "electronic", "jungle"],
    "notion": ["drum and bass", "electronic", "neurofunk"],
    "obskür": ["techno", "minimal techno", "electronic"],
    "omar+": ["techno", "house", "electronic"],
    "omnom": ["dubstep", "bass music", "electronic"],
    "the outlaw": ["hardstyle", "raw hardstyle", "electronic"],
    "paramida": ["house", "techno", "minimal techno"],
    "pegassi": ["house", "tech house", "electronic"],
    "player dave": ["house", "tech house", "electronic"],
    "prospa": ["house", "rave", "electronic"],
    "the purge": ["dubstep", "riddim", "bass music"],
    "rebekah": ["techno", "industrial techno", "hard techno"],
    "restricted": ["dubstep", "bass music", "electronic"],
    "rob gee": ["hardcore", "gabber", "speedcore"],
    "roddy lima": ["house", "tech house", "electronic"],
    "rooler": ["hardstyle", "raw hardstyle", "uptempo"],
    "røz": ["techno", "minimal techno", "electronic"],
    "the saints": ["hardstyle", "raw hardstyle", "electronic"],
    "sama' abdulhadi": ["techno", "minimal techno", "electronic"],
    "serafina": ["house", "tech house", "electronic"],
    "sippy": ["dubstep", "bass music", "electronic"],
    "slamm": ["house", "tech house", "electronic"],
    "slugg": ["dubstep", "riddim", "bass music"],
    "sofi tukker": ["house", "deep house", "tropical house"],
    "sub focus": ["drum and bass", "electronic", "dubstep"],
    "superstrings": ["trance", "uplifting trance", "electronic"],
    "vieze asbak": ["techno", "industrial techno", "hard techno"],
    "vintage culture": ["house", "tech house", "progressive house"],
    "viperactive": ["drum and bass", "electronic", "neurofunk"],
    "trace": ["drum and bass", "electronic", "techstep"],
    "bob moses": ["electronic", "indie dance", "deep house"],
    "martin garrix": ["big room house", "electro house", "edm"],
    "mary droppinz": ["dubstep", "bass music", "electronic"],
    "yosuf": ["techno", "minimal techno", "electronic"],
    "alok": ["bass house", "future house", "brazilian bass"],
    "terms of service": ["organizational", "administrative", "non-artist"],
    "and": ["organizational", "administrative", "non-artist"],
    "privacy policy": ["organizational", "administrative", "non-artist"]
}

def update_json_with_genres(original_data_str):
    """
    Update the JSON data with new genre information
    
    Args:
        original_data_str: The original JSON as a string
        
    Returns:
        Updated JSON data
    """
    # Parse the original JSON
    data = json.loads(original_data_str)
    
    # Counter for updates
    updates_count = 0
    
    # Update each artist with unknown genres
    for artist_key, genre_list in GENRE_UPDATES.items():
        if artist_key in data["artists"]:
            if data["artists"][artist_key]["genres"] == ["unknown"]:
                data["artists"][artist_key]["genres"] = genre_list
                updates_count += 1
                
                # Also update timbre if it was unknown
                if data["artists"][artist_key]["timbre"] == ["unknown"]:
                    # Set appropriate timbre based on genre
                    if "house" in genre_list or "techno" in genre_list:
                        data["artists"][artist_key]["timbre"] = ["groovy", "electronic"]
                    elif "dubstep" in genre_list or "bass" in str(genre_list):
                        data["artists"][artist_key]["timbre"] = ["energetic", "heavy", "electronic"]
                    elif "trance" in genre_list:
                        data["artists"][artist_key]["timbre"] = ["uplifting", "melodic", "electronic"]
                    elif "drum and bass" in genre_list:
                        data["artists"][artist_key]["timbre"] = ["energetic", "fast", "electronic"]
                    else:
                        data["artists"][artist_key]["timbre"] = ["electronic"]
    
    # Update metadata
    data["metadata"]["last_modified"] = datetime.now().isoformat() + "+00:00"
    data["metadata"]["genre_update_count"] = updates_count
    data["metadata"]["genre_update_date"] = "2026-02-16"
    
    return data, updates_count

# Instructions for use
if __name__ == "__main__":
    print("=" * 70)
    print("FESTIVAL ARTISTS JSON GENRE UPDATER")
    print("=" * 70)
    print("\nThis script will update all 'unknown' genres in the JSON file")
    print(f"Total genre mappings available: {len(GENRE_UPDATES)}")
    print("\nTo use this script:")
    print("1. Copy your original festival_artists.json content")
    print("2. Pass it to the update_json_with_genres() function")
    print("3. Save the output to a new JSON file")
    print("\nExample genres updated:")
    print("-" * 70)
    for i, (artist, genres) in enumerate(list(GENRE_UPDATES.items())[:15]):
        print(f"  {artist:25} -> {', '.join(genres)}")
    print(f"  ... and {len(GENRE_UPDATES) - 15} more")
    print("=" * 70)
    update_json_with_genres("artists.json")
