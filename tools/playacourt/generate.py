"""`pc.py generate`: draft card rules with Claude.

What gets written: only fields that are empty or whose "why" is AI draft / Placeholder.
Anything you've marked Form, Known, Balance or Ethos is passed to the model as fixed and
never overwritten. Locked cards are skipped entirely.

Inputs to the model: the "Ability ethos" Google Doc in Drive/PlayaCourt (read fresh on each
run, so edits there apply immediately), every applicable guideline (Guidelines tab + the
card's own "Card guidelines"), the sign-up answers, and a one-line summary of every other
card so it can balance against the deck.
"""
import functools
import json

from . import rules, schema
from .store import load_config


@functools.lru_cache(maxsize=1)
def ethos_text():
    from . import gapi
    doc = load_config().get("google", {}).get("ethos_doc_id")
    if not doc:
        raise SystemExit("Set [google] ethos_doc_id in private/config.toml (the ID in the "
                         "'Ability ethos' Google Doc URL).")
    return gapi.export_text(doc)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "class": {"type": "string", "enum": schema.CLASSES},
        "camp": {"type": "string", "description": "Printed camp, or empty for a Rogue."},
        "badge": {"type": "string", "description": "2-3 capital letters, or empty for a Rogue."},
        "power": {"type": "integer"},
        "tag1": {"type": "string", "enum": schema.TAGS},
        "tag2": {"type": "string", "enum": [""] + schema.TAGS},
        "scope": {"type": "string", "enum": schema.SCOPES},
        "timing": {"type": "string", "enum": schema.TIMINGS},
        "ability": {"type": "string"},
        "flavor": {"type": "string"},
        "rarity": {"type": "string", "enum": schema.RARITIES},
        "ability_value": {"type": "number", "description": "Average power the ability adds in a typical round."},
        "art_brief": {"type": "string", "description": "One sentence: who, doing what, where. No style words."},
        "notes": {"type": "string", "description": "Two or three sentences: why these choices, what was balanced against."},
    },
    "required": ["class", "camp", "badge", "power", "tag1", "tag2", "scope", "timing", "ability",
                 "flavor", "rarity", "ability_value", "art_brief", "notes"],
    "additionalProperties": False,
}

SYSTEM = """You design cards for Playa Court, a gifted card game where every card is a real person at a festival.
Follow the ability ethos exactly; it is the source of truth for classes, tags, wording, sizes and Rogues.
Apply every guideline you are given. Where a guideline conflicts with the ethos, follow the ethos and say so in notes.
Fields listed as FIXED were chosen by the designer: return them unchanged.
Balance against the rest of the deck: avoid duplicating an existing ability, and keep power + ability value in line with cards of the same class."""


def _owned(card, field):
    """True when the designer has claimed this field, so generate must not change it.
    A claimed field stays fixed even when blank (e.g. no camp = Rogue, a deliberate single tag)."""
    src = schema.SRC_OF[field]
    blank = str(card.get(field, "")).strip() == ""
    if field == "ability_value":  # an estimate: refresh it whenever the ability is regenerated
        return not blank and _owned(card, "ability")
    if src is None:
        return not blank
    return card.get(src, "") in schema.OWNED_SOURCES


def _deck_line(c):
    tags = " ".join(f"[{t}]" for t in rules.tags(c))
    lbl = rules.label(c)
    return f"{c['card_id']} {c.get('name')}: {c.get('class')} {c.get('power')} {tags} | {lbl} {c.get('ability')}".strip()


def build_request(card, wb):
    fixed = {f: card.get(f) for f in schema.GENERATED_FIELDS if _owned(card, f)}
    form = {k: card.get(k) for k in ("name", "class_requested", "camp_raw", "known_for_1", "known_for_2",
                                      "known_for_3", "my_input") if card.get(k)}
    deck = [_deck_line(c) for c in wb.cards()
            if c["card_id"] != card["card_id"] and c.get("status") not in ("withdrawn", "submitted") and c.get("ability")]
    guides = wb.guidelines_for(card)
    user = "\n\n".join([
        f"<ethos>\n{ethos_text()}\n</ethos>",
        "<deck>\n" + ("\n".join(deck) or "(no other cards yet)") + "\n</deck>",
        "<guidelines>\n" + ("\n".join(guides) or "(none)") + "\n</guidelines>",
        f"<card id=\"{card['card_id']}\">\nSign-up answers: {json.dumps(form, ensure_ascii=False)}\n"
        f"FIXED fields (return unchanged): {json.dumps(fixed, ensure_ascii=False)}\n</card>",
        "Design this card.",
    ])
    return user


def generate_card(card, wb, client=None):
    import anthropic
    client = client or anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=wb.settings().get("gen_model") or "claude-opus-5-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": build_request(card, wb)}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"{card['card_id']}: model declined ({getattr(resp.stop_details, 'category', None)})")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"{card['card_id']}: response cut off")
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))

    updates = {}
    for f in schema.GENERATED_FIELDS:
        if _owned(card, f):
            continue
        updates[f] = str(data[f]) if f != "ability_value" else f"{data[f]:g}"
        src = schema.SRC_OF[f]
        if src and card.get(src, "") not in schema.OWNED_SOURCES:
            updates[src] = "AI draft"
    updates["ai_notes"] = data["notes"]
    return updates
