import zlib

PALETTE = [
    "#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c", "#38d9a9",
    "#4dabf7", "#748ffc", "#b197fc", "#f783ac", "#a1887f",
]

ICONS = [
    "🎵", "🎶", "🔊", "📢", "🎤", "🎧", "🥁", "🎺", "🎸", "🎹",
    "😂", "🤣", "😎", "😡", "😱", "🤔", "👏", "👍", "💀", "👻",
    "🤖", "👽", "🐸", "🐱", "🐶", "🦆", "🐐", "🔥", "💥", "⚡",
    "💣", "🚨", "🎮", "🕹️", "🏆", "⚔️", "🎉", "❤️", "💩", "🍕",
    "🍺", "🚀", "🌟", "📺", "🎬", "📞", "⏰", "❓",
]

DEFAULT_ICON = "🎵"


def default_color(name):
    return PALETTE[zlib.crc32(name.encode("utf-8")) % len(PALETTE)]


class Categories:
    def __init__(self, data=None):
        self.data = data if data is not None else {}

    def color(self, name):
        return (self.data.get(name) or {}).get("color") or default_color(name)

    def icon(self, name):
        return (self.data.get(name) or {}).get("icon") or DEFAULT_ICON

    def names(self, sounds):
        used = {s["category"] for s in sounds if s["category"]}
        return sorted(used | set(self.data), key=str.lower)

    def set(self, name, color=None, icon=None):
        entry = self.data.setdefault(name, {})
        if color:
            entry["color"] = color
        if icon:
            entry["icon"] = icon

    def rename(self, old, new, sounds):
        if old == new:
            return
        entry = self.data.pop(old, None)
        if entry is not None:
            self.data[new] = entry
        for s in sounds:
            if s["category"] == old:
                s["category"] = new

    def delete(self, name, sounds):
        self.data.pop(name, None)
        for s in sounds:
            if s["category"] == name:
                s["category"] = ""
