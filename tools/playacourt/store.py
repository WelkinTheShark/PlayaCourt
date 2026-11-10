"""The card workbook: the Google Sheet "Playa Court Cards" in Drive/PlayaCourt.

This is the only place card data lives. Scripts read it, write their results back to it,
and keep nothing on disk except gitignored work files (drafting packets/drafts) and
short-lived temp files while rendering.

Tabs are read by header text, so column order in the sheet doesn't matter, and columns added
by `upgrade-sheet` simply appear at the end.
"""
import os
import re
import tomllib
from pathlib import Path

from . import schema

REPO = Path(__file__).resolve().parents[2]
PRIVATE = REPO / "private"          # gitignored: credentials, config, work files
SECRETS = PRIVATE / "secrets"
CONFIG = PRIVATE / "config.toml"
WORK = PRIVATE / "work"             # packets/ and drafts/ for Claude Code drafting

ROGUE_ANSWERS = {"", "none", "na", "n/a", "no", "nope", "wherever", "anywhere", "open camping",
                 "open camp", "staff", "staff camping", "volunteer", "volunteers", "crew", "tbd", "?"}


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


def norm(s):
    """Loose match key for camp names: case, 'the', punctuation and spaces ignored."""
    s = re.sub(r"^\s*the\s+", "", str(s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def is_rogue_answer(camp_raw, person_name=""):
    raw = str(camp_raw or "").strip().lower()
    if raw in ROGUE_ANSWERS or any(w in raw for w in ("staff", "volunteer")):
        return True
    return bool(person_name) and norm(raw) == norm(person_name)


class _Tab:
    """One sheet tab: rows as dicts keyed by code field names."""

    def __init__(self, name, rows, header, header_of):
        self.name, self.header, self.header_of = name, header, header_of
        to_key = {h: k for k, h in header_of.items()}
        self.rows = []
        for r in rows:
            d = {k: "" for k in header_of}
            d.update({to_key[h]: v for h, v in r.items() if h in to_key})
            self.rows.append(d)
        self.missing = [h for h in header_of.values() if h not in header]


class Workbook:
    """Reads every tab once; update/add methods write straight back to the sheet.

    For offline tests pass tables={tab: (rows, header)} and writer=None (writes stay in memory).
    """

    def __init__(self, spreadsheet_id=None, tables=None, writer="google"):
        if tables is None:
            from . import gapi  # needs the Google client libraries
            self.g = gapi
            self.id = spreadsheet_id or sheet_id()
            read = lambda tab: gapi.read_tab(self.id, tab, missing_ok=True)
        else:
            self.g = None if writer in (None, "google") else writer
            self.id = None
            read = lambda tab: tables.get(tab, ([], []))
        self.cards_tab = _Tab(schema.TAB_CARDS, *read(schema.TAB_CARDS), schema.CARD_HEADER)
        if not self.cards_tab.header:
            raise SystemExit("The Cards tab is empty or missing.")
        core = {"Card ID", "Status", "Name"} & set(self.cards_tab.missing)
        if core:
            raise SystemExit(f"Cards tab is missing core columns: {', '.join(sorted(core))}")
        self.camps_tab = _Tab(schema.TAB_CAMPS, *read(schema.TAB_CAMPS), schema.CAMP_HEADER)
        self.people_tab = _Tab(schema.TAB_PEOPLE, *read(schema.TAB_PEOPLE), schema.PEOPLE_HEADER)
        self.guides_tab = _Tab(schema.TAB_GUIDELINES, *read(schema.TAB_GUIDELINES), schema.GUIDELINE_HEADER)

        settings, _ = read(schema.TAB_SETTINGS)
        s_key = {label: k for k, label in schema.SETTINGS_LABEL.items()}
        self._settings = dict(schema.SETTINGS_DEFAULTS)
        self._settings_rows = {}
        for i, r in enumerate(settings):
            k = s_key.get(r.get("Setting", ""))
            if k:
                self._settings[k] = r.get("Value", "")
                self._settings_rows[k] = i
        self._cards = [c for c in self.cards_tab.rows if c["card_id"]]

    # ---------- reading ----------
    def cards(self):
        return self._cards

    def camps(self):
        return [c for c in self.camps_tab.rows if c["camp"]]

    def people(self):
        return {p["card_id"]: p for p in self.people_tab.rows if p.get("card_id")}

    def settings(self):
        return self._settings

    def needs_upgrade(self):
        return {t.name: t.missing for t in (self.cards_tab, self.camps_tab, self.people_tab, self.guides_tab)
                if t.missing}

    def locked(self, row):
        return str(row.get("locked", "")).strip().lower() in schema.YES

    def find_camp(self, name):
        """Camps row whose name or any alias loosely matches `name`, else None."""
        key = norm(name)
        if not key:
            return None
        for c in self.camps():
            names = [c["camp"]] + [a for a in c.get("aliases", "").split(",") if a.strip()]
            if key in {norm(n) for n in names}:
                return c
        return None

    def camp_for(self, card):
        return (self.find_camp(card.get("camp_key")) or self.find_camp(card.get("camp"))
                or self.find_camp(card.get("camp_raw")))

    def camp_members(self, camp):
        return [c for c in self._cards if self.camp_for(c) is camp]

    def guidelines_for(self, card):
        """Everything that should steer this card, broadest first, the card's own last
        (later lines win where they conflict)."""
        out = []
        for g in self.guides_tab.rows:
            if g.get("active", "").strip().lower() not in schema.YES or not g.get("guideline"):
                continue
            kind, which = g.get("applies_to", ""), g.get("which", "").strip()
            camp = self.camp_for(card)
            hit = (kind == "All cards"
                   or (kind == "Camp" and (self.find_camp(which) is camp if camp else
                                           norm(which) in (norm(card.get("camp")), norm(card.get("camp_raw")))))
                   or (kind == "Class" and which.lower() == card.get("class", "").lower())
                   or (kind == "Tag" and which.strip("[]").lower() in {t.lower() for t in (card.get("tag1"), card.get("tag2")) if t})
                   or (kind == "Card ID" and which.lower() == card["card_id"].lower()))
            if hit:
                out.append(f"[{kind}{': ' + which if which else ''}] {g['guideline']}")
        camp = self.camp_for(card)
        if camp:
            for k, label in (("theme", "theme"), ("rule_themes", "rule themes")):
                if camp.get(k):
                    out.append(f"[Camp {camp['camp']} {label}] {camp[k]}")
        if card.get("guidelines"):
            out.append(f"[This card] {card['guidelines']}")
        return out

    # ---------- writing ----------
    def _write(self, tab, index, fields):
        for k, v in fields.items():
            tab.rows[index][k] = v
        if self.g:
            self.g.write_cells(self.id, tab.name, tab.header, index,
                               {tab.header_of[k]: v for k, v in fields.items() if k in tab.header_of})

    def _append(self, tab, fields):
        row = {k: "" for k in tab.header_of}
        row.update(fields)
        tab.rows.append(row)
        if self.g:
            by_header = {tab.header_of[k]: v for k, v in row.items()}
            self.g.append_rows(self.id, tab.name, [[by_header.get(h, "") for h in tab.header]])
        return row

    def update(self, card_id, fields):
        for i, c in enumerate(self.cards_tab.rows):
            if c["card_id"] == card_id:
                self._write(self.cards_tab, i, fields)

    def add_card(self, fields):
        row = self._append(self.cards_tab, fields)
        self._cards.append(row)
        return row

    def add_person(self, fields):
        return self._append(self.people_tab, fields)

    def add_camp(self, fields):
        return self._append(self.camps_tab, fields)

    def update_camp(self, name, fields):
        camp = self.find_camp(name)
        if not camp:
            raise SystemExit(f"No camp '{name}' on the Camps tab.")
        self._write(self.camps_tab, self.camps_tab.rows.index(camp), fields)
        return camp

    def set_setting(self, key, value):
        self._settings[key] = value
        if not self.g:
            return
        if key in self._settings_rows:
            self.g.write_cells(self.id, schema.TAB_SETTINGS, ["Setting", "Value"],
                               self._settings_rows[key], {"Value": value})
        else:
            self.g.append_rows(self.id, schema.TAB_SETTINGS, [[schema.SETTINGS_LABEL[key], value, ""]])

    def next_card_id(self):
        prefix = self._settings.get("set_code") or "PC1"
        nums = [int(m.group(1)) for c in self._cards
                if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", c["card_id"]))]
        return f"{prefix}-{(max(nums) if nums else 0) + 1:03d}"


def open_workbook(_args=None):
    return Workbook()
