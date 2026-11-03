from soundpad_linux.categories import DEFAULT_ICON, PALETTE, Categories, default_color


def sounds():
    return [
        {"id": 1, "category": "Memes"},
        {"id": 2, "category": "Memes"},
        {"id": 3, "category": ""},
        {"id": 4, "category": "Games"},
    ]


def test_default_color_is_stable():
    assert default_color("Memes") == default_color("Memes")
    assert default_color("Memes") in PALETTE


def test_defaults_and_custom_meta():
    c = Categories({"Memes": {"color": "#123456", "icon": "🐸"}})
    assert c.color("Memes") == "#123456"
    assert c.icon("Memes") == "🐸"
    assert c.color("Games") == default_color("Games")
    assert c.icon("Games") == DEFAULT_ICON


def test_names_include_empty_categories():
    c = Categories({"Empty": {}})
    assert c.names(sounds()) == ["Empty", "Games", "Memes"]


def test_rename_moves_meta_and_sounds():
    data = sounds()
    c = Categories({"Memes": {"icon": "😂"}})
    c.rename("Memes", "Funny", data)
    assert c.icon("Funny") == "😂"
    assert "Memes" not in c.data
    assert [s["category"] for s in data] == ["Funny", "Funny", "", "Games"]


def test_delete_clears_sounds():
    data = sounds()
    c = Categories({"Memes": {"icon": "😂"}})
    c.delete("Memes", data)
    assert "Memes" not in c.data
    assert [s["category"] for s in data] == ["", "", "", "Games"]
