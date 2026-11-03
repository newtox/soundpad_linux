def fmt_duration(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(round(seconds)))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_duration(text):
    if not text:
        return None
    try:
        parts = [float(p.replace(",", ".")) for p in str(text).strip().split(":")]
    except ValueError:
        return None
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total if total > 0 else None


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
