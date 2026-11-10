"""`pc.py intake`: copy new sign-up responses into the processing sheet.

Reads the linked Form responses Sheet (Settings → Form responses sheet / tab), and for each
response not imported before (matched on the response timestamp):
- Cards: a new row (next card ID, status submitted) with the sign-up answers; anything the
  form asked that isn't mapped goes to Form extras.
- People (private): contact details, photo link and photo consent.
- Camps: the camp is matched by name or alias. Unknown camps get a new row with
  Status = new for review. Answers that aren't real camps (staff, volunteer, none, their own
  name …) make the card a Rogue (Camp: why = Ethos).
"""
import re

from . import schema
from .store import is_rogue_answer, norm


def map_columns(header):
    """{field key: response column header} using schema.FORM_MAP, plus unmapped columns."""
    used, mapping = set(), {}
    for key, phrases in schema.FORM_MAP:
        for h in header:
            if h in used or not h:
                continue
            if any(p in h.lower() for p in phrases):
                mapping[key] = h
                used.add(h)
                break
    extras = [h for h in header if h and h not in used]
    return mapping, extras


def _drive_id(value):
    m = re.search(r"(?:id=|/d/)([A-Za-z0-9_-]{20,})", value or "")
    return m.group(1) if m else (value or "").strip()


def _class(value):
    for c in schema.CLASSES:
        if c.lower() in (value or "").lower():
            return c
    return ""


def response_key(timestamp, name):
    """Responses are identified by their timestamp (unique per submission), falling back to
    the name only when the form has no timestamp. Renaming a card later doesn't re-import it."""
    ts = str(timestamp or "").strip()
    return f"ts:{ts}" if ts else f"name:{norm(name)}"


def run(wb, rows, header, dry_run=False):
    mapping, extras = map_columns(header)
    seen = {response_key(p.get("form_timestamp"), c.get("name"))
            for c in wb.cards() for p in [wb.people().get(c["card_id"], {})] if p.get("form_timestamp")}
    added, new_camps, rogues = [], [], []
    for r in rows:
        get = lambda k: (r.get(mapping[k], "") if k in mapping else "").strip()
        name = get("name") or get("full_name")
        if not name:
            continue
        key = response_key(get("form_timestamp"), name)
        if key in seen:
            continue
        seen.add(key)
        cid = wb.next_card_id() if not dry_run else f"(new {len(added) + 1})"
        camp_raw = get("camp_raw")
        card = {
            "card_id": cid, "status": "submitted", "name": name,
            "class_requested": _class(get("class_requested")), "camp_raw": camp_raw,
            "known_for_1": get("known_for_1"), "known_for_2": get("known_for_2"), "known_for_3": get("known_for_3"),
            "form_extras": "; ".join(f"{h}: {r.get(h, '').strip()}" for h in extras if r.get(h, "").strip()),
        }
        if get("class_requested") and not card["class_requested"]:
            card["form_extras"] = f"Class answer: {get('class_requested')}; " + card["form_extras"]
        camp = wb.find_camp(camp_raw)
        if camp:
            card["camp_key"] = camp["camp"]
        elif is_rogue_answer(camp_raw, name):
            card.update(camp="", badge="", camp_src="Ethos")
            rogues.append(f"{cid} {name} ({camp_raw or 'blank'})")
        elif camp_raw:
            if not dry_run:
                wb.add_camp({"camp": camp_raw.strip(), "status": "new"})
            card["camp_key"] = camp_raw.strip()
            if camp_raw.strip() not in new_camps:
                new_camps.append(camp_raw.strip())
        person = {"card_id": cid, "full_name": get("full_name"), "email": get("email"), "phone": get("phone"),
                  "photo_file_id": _drive_id(get("photo_file_id")), "photo_consent": get("photo_consent"),
                  "form_timestamp": get("form_timestamp")}
        if not dry_run:
            wb.add_card(card)
            wb.add_person(person)
        added.append(f"{cid} {name}")
    return {"mapping": mapping, "extras": extras, "added": added, "new_camps": new_camps, "rogues": rogues}
