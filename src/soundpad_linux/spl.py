import html
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlparse

from .constants import AUDIO_EXT
from .util import parse_duration, to_int

ALL_CATEGORY_NAMES = {"all sounds", "alle sounds", "all", "alle"}


def split_any_path(p):
    return [x for x in re.split(r"[\\/]+", p) if x]


def is_windows_path(p):
    return bool(re.match(r"^[A-Za-z]:[\\/]", p)) or p.startswith("\\\\")


def url_to_path(url):
    url = url.strip()
    if url.lower().startswith("file:"):
        parsed = urlparse(url)
        path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", path):
            path = path[1:]
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            path = f"\\\\{parsed.netloc}{path}"
        return path
    return url


def stem_of(p):
    if is_windows_path(p) or "\\" in p:
        return PureWindowsPath(p).stem
    return Path(p).stem


def read_text_any(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def _sound_from_attrs(attrs, category=""):
    path = url_to_path(attrs.get("url") or attrs.get("path") or "")
    title = (attrs.get("title") or "").strip() or stem_of(path)
    return {
        "title": title,
        "path": path,
        "orig": path,
        "category": category,
        "duration": parse_duration(attrs.get("duration")),
        "plays": to_int(attrs.get("playCount")),
    }


def parse_spl(file_path):
    text = read_text_any(file_path)
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _parse_spl_regex(text)

    parent = {child: p for p in root.iter() for child in p}
    url_sounds = [el for el in root.iter("Sound") if el.get("url") or el.get("path")]
    total = len(url_sounds)

    ref_ids = []
    categories = []
    for cat in root.iter("Category"):
        name = (cat.get("name") or "").strip()
        refs = [
            int(s.get("id"))
            for s in cat.findall("Sound")
            if not s.get("url") and (s.get("id") or "").isdigit()
        ]
        ref_ids.extend(refs)
        categories.append((name, refs))
    zero_based = bool(ref_ids) and min(ref_ids) == 0

    keys = []
    for pos, el in enumerate(url_sounds):
        own = el.get("index") or el.get("id")
        if own and own.isdigit():
            keys.append(int(own))
        else:
            keys.append(pos if zero_based else pos + 1)

    cat_of = {}
    for name, refs in categories:
        if not name or name.lower() in ALL_CATEGORY_NAMES:
            continue
        if total and len(set(refs)) >= total:
            continue
        for r in refs:
            cat_of.setdefault(r, name)

    sounds = []
    for el, key in zip(url_sounds, keys, strict=True):
        p = parent.get(el)
        category = ""
        if p is not None and p.tag == "Category":
            name = (p.get("name") or "").strip()
            if name.lower() not in ALL_CATEGORY_NAMES:
                category = name
        if not category:
            category = cat_of.get(key, "")
        sounds.append(_sound_from_attrs(dict(el.attrib), category))
    return sounds


def _parse_spl_regex(text):
    sounds = []
    for tag in re.findall(r"<Sound\s[^>]*>", text):
        attrs = {k: html.unescape(v) for k, v in re.findall(r'(\w+)\s*=\s*"([^"]*)"', tag)}
        if attrs.get("url") or attrs.get("path"):
            sounds.append(_sound_from_attrs(attrs))
    return sounds


def build_file_index(folders):
    index = {}
    for folder in folders:
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in AUDIO_EXT:
                    index.setdefault(f.lower(), []).append(os.path.join(root, f))
    return index


def _suffix_score(candidate, parts):
    cp = [x.lower() for x in split_any_path(candidate)]
    n = 0
    while n < min(len(cp), len(parts)) and cp[-1 - n] == parts[-1 - n]:
        n += 1
    return n


def resolve_missing(sounds, folders):
    index = build_file_index(folders)
    fixed = 0
    for s in sounds:
        if os.path.isfile(s["path"]):
            continue
        parts = [x.lower() for x in split_any_path(s.get("orig") or s["path"])]
        if not parts:
            continue
        candidates = index.get(parts[-1], [])
        if candidates:
            s["path"] = max(candidates, key=lambda c: _suffix_score(c, parts))
            fixed += 1
    return fixed
