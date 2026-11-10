"""Card drafting through Claude Code (no API calls).

    pc.py packet PC1-007   → private/work/packets/PC1-007.md   (everything needed to design the card)
    (Claude Code reads the packet, follows .claude/skills/playacourt-cards/SKILL.md,
     and writes private/work/drafts/PC1-007.json)
    pc.py apply PC1-007    → validates the draft and writes it to the sheet

What gets written: only fields that are empty or whose "why" is AI draft / Placeholder.
Anything marked Form, Known, Balance or Ethos is listed as FIXED in the packet and never
overwritten. Locked cards are refused. Camp and badge always follow the Camps tab.
People-tab data (contact details) is never put in a packet.
"""
import functools
import json

from . import rules, schema
from .store import WORK, load_config

PACKETS, DRAFTS = WORK / "packets", WORK / "drafts"

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
}


@functools.lru_cache(maxsize=1)
def ethos_text():
    from . import gapi
    doc = load_config().get("google", {}).get("ethos_doc_id")
    if not doc:
        raise SystemExit("Set [google] ethos_doc_id in private/config.toml (the ID in the "
                         "'Ability ethos' Google Doc URL).")
    return gapi.export_text(doc)


def _owned(card, field):
    """True when the designer has claimed this field, so drafting must not change it.
    A claimed field stays fixed even when blank (e.g. no camp = Rogue, a deliberate single tag)."""
    src = schema.SRC_OF[field]
    blank = str(card.get(field, "")).strip() == ""
    if field == "ability_value":  # an estimate: refresh it whenever the ability is redrafted
        return not blank and _owned(card, "ability")
    if src is None:
        return not blank
    return card.get(src, "") in schema.OWNED_SOURCES


def _deck_line(c):
    tags = " ".join(f"[{t}]" for t in rules.tags(c))
    lbl = rules.label(c)
    return f"{c['card_id']} {c.get('name')}: {c.get('class')} {c.get('power')} {tags} | {lbl} {c.get('ability')}".strip()


def camp_fixed(card, wb):
    """Camp/badge dictated by the Camps tab, or {} when the camper's camp isn't resolved."""
    camp = wb.camp_for(card)
    if not camp:
        return {}
    if str(camp.get("rogue", "")).strip().lower() in schema.YES:
        return {"camp": "", "badge": ""}
    return {"camp": camp["camp"], "badge": camp.get("badge", "")}


def fixed_fields(card, wb):
    fixed = {f: card.get(f) for f in schema.GENERATED_FIELDS if _owned(card, f)}
    if card.get("camp_src", "") not in schema.OWNED_SOURCES:
        fixed.update(camp_fixed(card, wb))
    return fixed


def _section(title, body):
    return f"## {title}\n\n{body.strip() or '(none)'}\n"


def build_packet(card, wb, note=None):
    cid = card["card_id"]
    person = {schema.CARD_HEADER[k]: card[k] for k in
              ("name", "class_requested", "camp_raw", "known_for_1", "known_for_2", "known_for_3",
               "form_extras", "my_input", "art_notes") if card.get(k)}
    camp = wb.camp_for(card)
    if camp:
        prof = {schema.CAMP_HEADER[k]: camp[k] for k in schema.CAMP_FIELDS
                if camp.get(k) and k not in ("status", "locked")}
        mates = [_deck_line(m) if m.get("ability") else f"{m['card_id']} {m.get('name')}: (not drafted yet)"
                 for m in wb.camp_members(camp) if m["card_id"] != cid]
        camp_txt = "\n".join(f"- **{k}:** {v}" for k, v in prof.items())
        camp_txt += "\n\nOther members:\n" + ("\n".join(f"- {m}" for m in mates) or "- (none yet)")
    else:
        camp_txt = (f"Not on the Camps tab yet (they wrote: {card.get('camp_raw') or 'nothing'}). "
                    "Treat as unresolved: ask the user, or run `pc.py camps` first.")
    guides = wb.guidelines_for(card)
    if note:
        guides.append(f"[This run only] {note}")
    deck = [_deck_line(c) for c in wb.cards()
            if c["card_id"] != cid and c.get("status") not in ("withdrawn", "submitted") and c.get("ability")]
    draft_path = DRAFTS / f"{cid}.json"
    return "\n".join([
        f"# Card packet: {cid} · {card.get('name', '')}\n",
        _section("Your task", f"""Design this card following the skill `.claude/skills/playacourt-cards/SKILL.md`
and the ethos below. Write one JSON object to `{draft_path.as_posix()}` with exactly these keys:
{', '.join(OUTPUT_SCHEMA['required'])}.
Return FIXED fields unchanged. Then run `python tools/pc.py apply {cid} --preview`."""),
        _section("The person (sign-up answers + designer notes)", "\n".join(f"- **{k}:** {v}" for k, v in person.items())),
        _section("Their camp", camp_txt),
        _section("Guidelines (broadest first; later lines win on conflict)", "\n".join(f"- {g}" for g in guides)),
        _section("FIXED fields (return unchanged)", json.dumps(fixed_fields(card, wb), ensure_ascii=False, indent=1)),
        _section("The rest of the deck", "\n".join(f"- {d}" for d in deck)),
        _section("Output schema", "```json\n" + json.dumps(OUTPUT_SCHEMA, indent=1) + "\n```"),
        _section("Ability ethos (the rulebook)", ethos_text()),
    ])


def write_packet(card, wb, note=None):
    PACKETS.mkdir(parents=True, exist_ok=True)
    path = PACKETS / f"{card['card_id']}.md"
    path.write_text(build_packet(card, wb, note), encoding="utf-8")
    return path


def validate_draft(data):
    errs = []
    if not isinstance(data, dict):
        return ["draft must be one JSON object"]
    for k in OUTPUT_SCHEMA["required"]:
        if k not in data:
            errs.append(f"missing '{k}'")
    for k, spec in OUTPUT_SCHEMA["properties"].items():
        if k not in data:
            continue
        v, t = data[k], spec["type"]
        ok = (isinstance(v, str) if t == "string" else
              isinstance(v, int) and not isinstance(v, bool) if t == "integer" else
              isinstance(v, (int, float)) and not isinstance(v, bool))
        if not ok:
            errs.append(f"'{k}' should be a {t}")
        elif "enum" in spec and v not in spec["enum"]:
            errs.append(f"'{k}' = {v!r} is not one of {spec['enum']}")
    extra = set(data) - set(OUTPUT_SCHEMA["properties"])
    if extra:
        errs.append(f"unexpected keys: {', '.join(sorted(extra))}")
    return errs


def apply_draft(card, wb, data):
    """Returns (updates, errors, warnings). Nothing is written here."""
    if wb.locked(card):
        return {}, [f"{card['card_id']} is locked"], []
    errs = validate_draft(data)
    if errs:
        return {}, errs, []
    data = dict(data)
    if card.get("camp_src", "") not in schema.OWNED_SOURCES:
        data.update(camp_fixed(card, wb))          # the Camps tab always wins for camp/badge
    from_camps = bool(camp_fixed(card, wb)) and card.get("camp_src", "") not in schema.OWNED_SOURCES
    updates = {}
    for f in schema.GENERATED_FIELDS:
        if _owned(card, f):
            continue
        v = data[f]
        updates[f] = f"{v:g}" if f == "ability_value" else str(v)
        src = schema.SRC_OF[f]
        if src == "camp_src" and from_camps:
            continue                                   # camp/badge follow the Camps tab, not the draft
        if src and card.get(src, "") not in schema.OWNED_SOURCES:
            updates[src] = "AI draft"
    camp = wb.camp_for(card)
    if camp:
        updates["camp_key"] = camp["camp"]
    updates["ai_notes"] = data["notes"]
    merged = dict(card, **updates)
    status = merged.get("status") if merged.get("status") not in ("", "submitted") else "drafting"
    e, w = rules.check(dict(merged, status=status))
    return updates, e, w
