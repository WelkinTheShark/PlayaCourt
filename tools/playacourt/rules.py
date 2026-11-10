"""Game facts derived from a card's fields, and the ability-ethos checks.

Nothing here is stored in the sheet: beats, symbols and colours are worked out from the
class every time, so changing a card's class can't leave a stale "Beats" line behind.
"""
import hashlib
import json
import re

from . import schema

# Each class beats exactly one other (index.html, "The class ring").
BEATS = {"Joker": "King", "King": "Knight", "Knight": "Queen", "Queen": "Page", "Page": "Joker"}

# Class colours and element symbols, sampled from the PC1 cards and the card back.
CLASS_STYLE = {
    "King":   {"band": "#D9A93A", "ink": "#7A5410", "symbol": "earth"},   # gold ▽ with bar
    "Queen":  {"band": "#4F8CC0", "ink": "#24609F", "symbol": "water"},   # blue ▽
    "Knight": {"band": "#D9653A", "ink": "#A8432A", "symbol": "fire"},    # red △
    "Page":   {"band": "#5FB37E", "ink": "#2E7D4F", "symbol": "air"},     # green △ with bar
    "Joker":  {"band": "#9B62C9", "ink": "#6D3A97", "symbol": "spirit"},  # purple ●
}
RARITY_SYMBOL = {"Common": "●", "Uncommon": "▲", "Rare": "★"}
COURT_RANK = {"King": "K", "Queen": "Q", "Knight": "Kn", "Page": "P"}

# Fields that change what is printed. Editing anything else never forces a re-render.
DRAWN_FIELDS = ["card_id", "status", "name", "class", "camp", "badge", "power", "tag1", "tag2",
                "scope", "timing", "ability", "flavor", "rarity", "element", "rank",
                "art_file_id", "art_focus"]
TEMPLATE_VERSION = "3"  # bump when render/card.html changes so every card re-renders


def tags(card):
    return [t for t in (card.get("tag1", ""), card.get("tag2", "")) if t]


def is_rogue(card):
    return not card.get("camp", "").strip()


def label(card):
    """The small coloured line above the ability, e.g. "Self:" or "Aura · This round:"."""
    parts = [p for p in (card.get("scope", ""), card.get("timing", "")) if p]
    return (" · ".join(parts) + ":") if parts else ""


def rules_hash(card):
    payload = {k: str(card.get(k, "")).strip() for k in DRAWN_FIELDS}
    payload["_template"] = TEMPLATE_VERSION
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def needs_render(card):
    return card.get("rendered_hash", "") != rules_hash(card)


def check(card):
    """Return (errors, warnings). Errors block approval; warnings are advice from the ethos."""
    e, w = [], []
    cls = card.get("class", "")
    status = card.get("status", "")
    if status in ("withdrawn", "submitted"):
        return e, w
    if not re.fullmatch(r"PC\d+-\d{3}", card.get("card_id", "")):
        e.append("card_id should look like PC1-007")
    if cls not in schema.CLASSES:
        e.append(f"class '{cls}' is not one of {', '.join(schema.CLASSES)}")

    try:
        power = int(str(card.get("power", "")).strip())
        if not 1 <= power <= 10:
            e.append("power must be 1–10")
        elif cls == "Joker" and power > 5:
            w.append("Jokers sit at power 1–5 (ethos §4)")
    except ValueError:
        e.append("power must be a whole number")

    tg = tags(card)
    if not tg:
        e.append("needs at least one tag")
    if len(tg) != len(set(tg)):
        e.append("tag1 and tag2 are the same")
    for t in tg:
        if t not in schema.TAGS:
            e.append(f"unknown tag '{t}'")

    if is_rogue(card) and card.get("badge", "").strip():
        e.append("Rogue (no camp) can't have a camp badge")
    if not is_rogue(card) and not re.fullmatch(r"[A-Z0-9]{2,3}", card.get("badge", "").strip()):
        w.append("camp badge should be 2–3 capital letters")

    if card.get("scope", "") not in schema.SCOPES:
        e.append("scope must be Self, Aura or blank")
    if card.get("timing", "") not in schema.TIMINGS:
        e.append("timing must be This round, If this wins, If this loses or blank")
    if card.get("rarity", "") not in schema.RARITIES:
        e.append("rarity must be Common, Uncommon or Rare")

    ab = card.get("ability", "").strip()
    if not ab:
        e.append("ability is empty")
    if len(ab) > 135:
        e.append(f"ability is {len(ab)} characters (max 135, ethos §7)")
    for t in re.findall(r"\[(\w+)\]", ab):
        if t not in schema.TAGS:
            e.append(f"ability mentions unknown tag [{t}]")
    if re.search(r"[−-]\d", ab) and cls not in ("Queen", "Joker"):
        w.append("minuses belong on Queens or Jokers only (ethos §1)")
    for phrase in ("either camp", "both camps", "your opponent's"):
        if phrase in ab.lower():
            w.append(f"'{phrase}' assumes two players; use 'any camp' / 'enemy' (ethos §7)")
    if re.search(r"\]\s+cards?\b", ab):
        w.append("leave out 'card' after a tag: 'All [Food] get +2' (ethos §7)")
    if "flip" in ab.lower():
        w.append("use 'rotate' for Burn Out, not 'flip'")

    el, rank = card.get("element", ""), str(card.get("rank", "")).strip()
    if el and el not in schema.ELEMENTS:
        e.append(f"unknown element '{el}'")
    if rank:
        if cls == "Joker" and rank != "0":
            e.append("Joker rank must be 0 (the Fool)")
        elif rank in COURT_RANK.values() and COURT_RANK.get(cls) != rank:
            e.append(f"court rank {rank} must match class {cls}")

    placeholders = [f[:-4] for f in schema.SRC_FIELDS if card.get(f) == "Placeholder"]
    if placeholders:
        msg = "placeholder: " + ", ".join(placeholders)
        (e if status in ("approved", "printed") else w).append(msg)
    return e, w


def check_deck(cards):
    """Checks across cards: duplicate IDs and names."""
    issues, seen_id, seen_name = [], {}, {}
    for c in cards:
        if c.get("status") == "withdrawn":
            continue
        for key, seen in (("card_id", seen_id), ("name", seen_name)):
            v = c.get(key, "").strip().lower()
            if v and v in seen:
                issues.append(f"duplicate {key} '{c.get(key)}' ({seen[v]} and {c.get('card_id')})")
            seen[v] = c.get("card_id")
    return issues
