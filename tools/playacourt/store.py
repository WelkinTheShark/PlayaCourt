"""The card workbook: the Google Sheet "Playa Court Cards" in Drive/PlayaCourt.

This is the only place card data lives. Scripts read it, write their results back to it,
and keep nothing on disk except short-lived temp files while rendering.
"""
import json
import os
import tomllib
from pathlib import Path

from . import schema

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / "private"          # gitignored: Google credentials + config only
SECRETS = PRIVATE / "secrets"
CONFIG = PRIVATE / "config.toml"



def load_config():
    if CONFIG.exists():
        with open(CONFIG, "rb") as f:
            return tomllib.load(f)
    return {}


def sheet_id():
    sid = os.environ.get("PC_SHEET_ID") or load_config().get("google", {}).get("spreadsheet_id")
    if not sid:
        raise SystemExit("Set [google] spreadsheet_id in private/config.toml (the ID in the "
                         "Playa Court Cards sheet URL), or the PC_SHEET_ID environment variable.")
    return sid


class Workbook:
    """Reads the Cards, People and Settings tabs once; update() writes straight back."""

    def __init__(self, spreadsheet_id=None):
        from . import gapi  # needs the Google client libraries
        self.g = gapi
        self.id = spreadsheet_id or sheet_id()

        rows, self._header = gapi.read_tab(self.id, schema.TAB_CARDS)
        to_key = {h: k for k, h in schema.CARD_HEADER.items()}
        missing = [h for h in schema.CARD_HEADER.values() if h not in self._header]
        if missing:
            raise SystemExit(f"Cards tab is missing columns: {', '.join(missing)}")
        self._cards = []
        for r in rows:
            card = {k: "" for k in schema.CARD_FIELDS}
            card.update({to_key[h]: v for h, v in r.items() if h in to_key})
            if card["card_id"]:
                self._cards.append(card)

        people, _ = gapi.read_tab(self.id, schema.TAB_PEOPLE)
        p_key = {h: k for k, h in schema.PEOPLE_HEADER.items()}
        self._people = {}
        for r in people:
            p = {p_key[h]: v for h, v in r.items() if h in p_key}
            if p.get("card_id"):
                self._people[p["card_id"]] = p

        guides, _ = gapi.read_tab(self.id, schema.TAB_GUIDELINES)
        g_key = {h: k for k, h in schema.GUIDELINE_HEADER.items()}
        self._guidelines = [{g_key[h]: v for h, v in r.items() if h in g_key} for r in guides]

        settings, _ = gapi.read_tab(self.id, schema.TAB_SETTINGS)
        s_key = {label: k for k, label in schema.SETTINGS_LABEL.items()}
        self._settings = dict(schema.SETTINGS_DEFAULTS)
        self._settings_rows = {}
        for i, r in enumerate(settings):
            k = s_key.get(r.get("Setting", ""))
            if k:
                self._settings[k] = r.get("Value", "")
                self._settings_rows[k] = i

    def cards(self):
        return self._cards

    def people(self):
        return self._people

    def settings(self):
        return self._settings

    def guidelines_for(self, card):
        """Active guidelines that apply to this card, broadest first, then its own column."""
        out = []
        for g in self._guidelines:
            if g.get("active", "").strip().lower() not in schema.YES or not g.get("guideline"):
                continue
            kind, which = g.get("applies_to", ""), g.get("which", "").strip().lower()
            hit = (kind == "All cards"
                   or (kind == "Camp" and which in (card.get("camp", "").strip().lower(),
                                                    card.get("camp_raw", "").strip().lower()))
                   or (kind == "Class" and which == card.get("class", "").strip().lower())
                   or (kind == "Tag" and which.strip("[]") in {t.lower() for t in (card.get("tag1"), card.get("tag2")) if t})
                   or (kind == "Card ID" and which == card["card_id"].lower()))
            if hit:
                out.append(f"[{kind}{': ' + g['which'] if g.get('which') else ''}] {g['guideline']}")
        if card.get("guidelines"):
            out.append(f"[This card] {card['guidelines']}")
        return out

    def locked(self, card):
        return card.get("locked", "").strip().lower() in schema.YES

    def update(self, card_id, fields):
        for i, c in enumerate(self._cards):
            if c["card_id"] == card_id:
                c.update(fields)
                self.g.write_cells(self.id, schema.TAB_CARDS, self._header, i,
                                   {schema.CARD_HEADER[k]: v for k, v in fields.items()})

    def set_setting(self, key, value):
        self._settings[key] = value
        if key in self._settings_rows:
            self.g.write_cells(self.id, schema.TAB_SETTINGS, ["Setting", "Value"],
                               self._settings_rows[key], {"Value": value})
        else:
            self.g.append_rows(self.id, schema.TAB_SETTINGS, [[schema.SETTINGS_LABEL[key], value, ""]])


def open_workbook(_args=None):
    return Workbook()
