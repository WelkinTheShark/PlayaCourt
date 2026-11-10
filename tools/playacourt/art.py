"""Card art: prompts, generation providers, and collecting finished images from Drive.

Every provider ends the same way: an image whose name starts with the card ID
(e.g. PC1-007-v2.png) lands in Drive "2 - Card Art / Inbox". `ingest-art` (or `refresh`)
then moves the newest one per card to "Chosen", renames it, and records it on the card.

Providers
- midjourney: Midjourney has no official API, and automating it breaks its terms, so
  `prompts` writes a paste-ready queue to a Google Doc next to the art folders. You run the
  prompts in Midjourney and save your pick to the Inbox.
- gemini: calls Google's image model and uploads results to the Inbox. Off until a key is
  set (paid API).
"""
import os
import re
import tempfile
from pathlib import Path

from . import schema
from .store import load_config

ID_RE = re.compile(r"^(PC\d+-\d{3})", re.I)
COLOUR_WORDS = {"King": "gold", "Queen": "blue", "Knight": "ember orange", "Page": "green", "Joker": "violet"}


def prompt_parts(card, settings, camp=None):
    """The pieces of a card's art prompt, most specific first:
    the card's Art brief → the camper's Art notes → the camp's Art setting and motifs →
    class colour → house Art style → Midjourney parameters. Edit those cells, never the prompt."""
    brief = card.get("art_brief", "").strip()
    if not brief:
        brief = f"portrait of {card.get('name', 'a festival-goer')}"
        known = [card.get(f"known_for_{i}", "") for i in (1, 2, 3)]
        known = [k for k in known if k]
        if known:
            brief += ", known for " + ", ".join(known)
    parts = [("brief", brief)]
    if card.get("art_notes", "").strip():
        parts.append(("camper", card["art_notes"].strip()))
    if camp and str(camp.get("rogue", "")).strip().lower() not in schema.YES:
        if camp.get("art_setting", "").strip():
            parts.append(("camp setting", camp["art_setting"].strip()))
        elif camp.get("camp"):
            parts.append(("camp setting", f"at their camp {camp['camp']}"))
        if camp.get("art_motifs", "").strip():
            parts.append(("camp motifs", camp["art_motifs"].strip()))
    elif card.get("camp"):
        parts.append(("camp setting", f"at their camp {card['camp']}"))
    colour = COLOUR_WORDS.get(card.get("class", ""), "")
    if colour:
        parts.append(("class colour", f"{colour} accents in the sky"))
    if settings.get("art_style", "").strip():
        parts.append(("house style", settings["art_style"].strip()))
    return parts


def build_prompt(card, settings, camp=None):
    text = ", ".join(p for _, p in prompt_parts(card, settings, camp))
    params = settings.get("mj_params", "").strip()
    if settings.get("mj_sref"):
        params += f" --sref {settings['mj_sref']}"
    return f"{text} {params}".strip()


def mj_queue_text(cards, people):
    lines = ["Midjourney queue", "",
             "For each card: paste the prompt into Midjourney. Add the person's reference photo as an "
             "omni-reference (--oref) only if the People tab says yes. Save your pick to "
             "PlayaCourt / 2 - Card Art / Inbox with a name starting with the card ID, e.g. PC1-007-v2.png. "
             "Then run: python tools/pc.py refresh", ""]
    for c in cards:
        p = people.get(c["card_id"], {})
        consent = p.get("photo_consent", "").strip().lower() in schema.YES
        lines += [f"{c['card_id']} · {c.get('name', '')} ({c.get('class', '')})",
                  c["mj_prompt"],
                  "Reference photo: " + ("yes (People tab)" if consent and p.get("photo_file_id") else "none"),
                  ""]
    return "\n".join(lines)


def generate_gemini(card, settings, people):
    """Generate one image with Gemini and upload it to the Inbox. Written against the
    google-genai SDK; not yet run (needs a paid key)."""
    cfg = load_config().get("gemini", {})
    key = os.environ.get("GEMINI_API_KEY") or cfg.get("api_key")
    if not key:
        raise SystemExit("Gemini is not set up: add [gemini] api_key to private/config.toml (paid API).")
    from google import genai
    from google.genai import types
    from . import gapi

    client = genai.Client(api_key=key)
    contents = [build_prompt(card, dict(settings, mj_params="", mj_sref="")) +
                ". Wide 13:8 landscape composition, no text, no border."]
    with tempfile.TemporaryDirectory() as tmp:
        p = people.get(card["card_id"], {})
        if p.get("photo_file_id") and p.get("photo_consent", "").strip().lower() in schema.YES:
            photo = gapi.download(p["photo_file_id"], Path(tmp) / "ref.jpg")
            contents.append(types.Part.from_bytes(data=photo.read_bytes(), mime_type="image/jpeg"))
        resp = client.models.generate_content(model=cfg.get("model", "gemini-2.5-flash-image"), contents=contents)
        n = 0
        for i, part in enumerate(resp.candidates[0].content.parts):
            if getattr(part, "inline_data", None):
                path = Path(tmp) / f"{card['card_id']}-gemini-{i}.png"
                path.write_bytes(part.inline_data.data)
                gapi.upload(path, settings["drive_inbox_id"], path.name)
                n += 1
    return n


def newest_per_card(files):
    """files: [{'id','name',...}] newest first → {card_id: file}."""
    out = {}
    for f in files:
        m = ID_RE.match(f["name"])
        if m and m.group(1).upper() not in out:
            out[m.group(1).upper()] = f
    return out


def ingest(wb, include_locked=False):
    """Inbox → Chosen. Returns the card IDs that got new art."""
    from . import gapi
    s = wb.settings()
    files = [f for f in gapi.list_folder(s["drive_inbox_id"]) if f["mimeType"].startswith("image/")]
    by_id = {c["card_id"].upper(): c for c in wb.cards()}
    done = []
    for cid, f in newest_per_card(files).items():
        card = by_id.get(cid)
        if not card:
            print(f"  skip {f['name']}: no card {cid} in the sheet")
            continue
        if wb.locked(card) and not include_locked:
            print(f"  skip {f['name']}: {cid} is locked (left in the Inbox)")
            continue
        ext = Path(f["name"]).suffix.lower() or ".png"
        name = f"{cid}-{re.sub(r'[^A-Za-z0-9]+', '-', card.get('name', '')).strip('-')}{ext}"
        gapi.move(f["id"], s["drive_final_id"], name)
        wb.update(card["card_id"], {"art_status": "chosen", "art_file_id": f["id"]})
        print(f"  {cid}: {f['name']} → Chosen/{name}")
        done.append(card["card_id"])
    return done


def _safe_name(card, ext):
    return f"{card['card_id']}-{re.sub(r'[^A-Za-z0-9]+', '-', card.get('name', '')).strip('-')}{ext}"


def set_art(wb, card, source, crop=None):
    """Make `source` this card's art: a local image file (uploaded to Chosen) or a Drive file
    ID / link (used where it is). Returns the Drive file ID."""
    import mimetypes
    from . import gapi
    path = Path(source)
    if path.is_file():
        ext = path.suffix.lower() or ".png"
        fid = gapi.upload(path, wb.settings()["drive_final_id"], _safe_name(card, ext),
                          mime=mimetypes.guess_type(path.name)[0] or "image/png")
    else:
        m = re.search(r"(?:id=|/d/)([A-Za-z0-9_-]{20,})", source)
        fid = m.group(1) if m else source.strip()
    fields = {"art_file_id": fid, "art_status": "chosen"}
    if crop:
        fields["art_focus"] = crop
    wb.update(card["card_id"], fields)
    return fid


def download_art(card, folder: Path):
    """Fetch the chosen art into a temp folder for rendering. None if there is no art yet."""
    fid = card.get("art_file_id", "")
    if not fid:
        return None
    from . import gapi
    return gapi.download(fid, folder / f"{card['card_id']}.img")
