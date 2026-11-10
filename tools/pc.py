#!/usr/bin/env python3
"""Playa Court card pipeline. All card data lives in Google Drive (PlayaCourt folder).
Card design is done by Claude Code following .claude/skills/playacourt-cards/SKILL.md;
these commands move data in and out of the sheet and Drive.

Set up / intake
  upgrade-sheet           add any missing tabs, columns, settings and folders (safe to re-run)
  intake [--dry-run]      copy new sign-up responses into Cards / People / Camps
  camps [--new]           show camps with their members, for coordinating themes
  set-camp NAME k=v ...   fill in a camp (badge=, theme=, rule_themes=, art_setting=, art_motifs=, rogue=, aliases=)

Drafting (Claude Code)
  packet IDS | --all      write private/work/packets/<ID>.md with everything needed to design the card
  apply IDS [--preview]   validate private/work/drafts/<ID>.json and save it to the sheet
  check [IDS]             ethos checks; results go to the Checks column
  balance [--set ...]     Monte Carlo balance test, with what-if overrides

Art and cards
  prompts [IDS]           build Midjourney prompts (sheet + "Midjourney queue" Doc)
  set-art ID FILE|DRIVE_ID [--crop "50% 30%"]   use this image as the card's art
  ingest-art              Inbox -> Chosen for each card with a new image
  render [IDS]            render print (bleed), print (no bleed) and display PNGs -> Drive
  refresh [IDS]           ingest-art + check + render
  export IDS --kind ...   save local copies (bleed | trim | display | all)

Locked cards (Locked = yes) and locked camps are never changed unless you pass --include-locked.
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playacourt import art, rules, schema, store  # noqa: E402

DRAFTABLE = {"submitted", "drafting", "review"}
KIND_FIELD = {"bleed": ("print_file_id", "drive_print_id", "print, with bleed"),
              "trim": ("trim_file_id", "drive_trim_id", "print, no bleed"),
              "display": ("display_file_id", "drive_display_id", "display")}


def pick(cards, ids):
    if not ids:
        return list(cards)
    want = {i.upper() for i in ids}
    found = [c for c in cards if c["card_id"].upper() in want]
    missing = want - {c["card_id"].upper() for c in found}
    if missing:
        raise SystemExit(f"Not in the sheet: {', '.join(sorted(missing))}")
    return found


def unlocked(wb, cards, a):
    keep = []
    for c in cards:
        if wb.locked(c) and not getattr(a, "include_locked", False):
            print(f"  {c['card_id']} is locked, skipped")
        else:
            keep.append(c)
    return keep


def warn_upgrade(wb):
    need = wb.needs_upgrade()
    if need:
        print("Note: the sheet is missing some columns/tabs. Run `python tools/pc.py upgrade-sheet`.")


# ---------------- set up / intake ----------------

def cmd_upgrade_sheet(a):
    from playacourt import gapi
    sid = store.sheet_id()
    tabs = gapi.list_tabs(sid)
    for tab, header in schema.TAB_HEADERS.items():
        if tab not in tabs:
            gapi.add_tab(sid, tab, header)
            print(f"  added tab {tab}")
            continue
        _, current = gapi.read_tab(sid, tab)
        new = [h for h in header if h not in current]
        if new:
            gapi.add_columns(sid, tab, current, new)
            print(f"  {tab}: added columns {', '.join(new)}")
    wb = store.Workbook(sid)
    s = wb.settings()
    for key, label, default, note in schema.SETTINGS:
        if key not in wb._settings_rows:
            gapi.append_rows(sid, schema.TAB_SETTINGS, [[label, default, note]])
            print(f"  Settings: added {label}")
    wb = store.Workbook(sid)
    s = wb.settings()
    if not s.get("drive_trim_id") and s.get("drive_renders_id"):
        fid = gapi.create_folder("Print (no bleed)", s["drive_renders_id"])
        wb.set_setting("drive_trim_id", fid)
        print("  created Drive folder 3 - Finished Cards / Print (no bleed)")
    print("Sheet is up to date.")


def cmd_intake(a):
    from playacourt import gapi, intake
    wb = store.open_workbook()
    warn_upgrade(wb)
    s = wb.settings()
    if not s.get("responses_sheet_id"):
        raise SystemExit("Set Settings → Form responses sheet to the ID of the linked responses Sheet "
                         "(Form → Responses → Link to Sheets, shared with this account).")
    rows, header = gapi.read_tab(s["responses_sheet_id"], s.get("responses_tab") or "Form Responses 1")
    rep = intake.run(wb, rows, header, dry_run=a.dry_run)
    print("Form columns → fields:")
    for k, h in rep["mapping"].items():
        print(f"  {h!r:50} → {k}")
    if rep["extras"]:
        print("  (kept in Form extras: " + ", ".join(repr(h) for h in rep["extras"]) + ")")
    verb = "Would add" if a.dry_run else "Added"
    print(f"\n{verb} {len(rep['added'])} submission(s)" + (":" if rep["added"] else "."))
    for x in rep["added"]:
        print(f"  {x}")
    if rep["new_camps"]:
        print("New camps (Status = new, need a theme/badge): " + ", ".join(rep["new_camps"]))
    if rep["rogues"]:
        print("Rogues (no real camp): " + ", ".join(rep["rogues"]))


def cmd_camps(a):
    wb = store.open_workbook()
    warn_upgrade(wb)
    camps = [c for c in wb.camps() if not a.new or c.get("status") == "new"]
    if not camps:
        print("No camps" + (" with Status = new." if a.new else " yet."))
    for camp in camps:
        members = wb.camp_members(camp)
        lock = " 🔒" if wb.locked(camp) else ""
        print(f"\n## {camp['camp']}{lock}  [{camp.get('status') or 'ok'}]")
        for k in schema.CAMP_FIELDS:
            if k not in ("camp", "status", "locked"):
                print(f"   {schema.CAMP_HEADER[k]}: {camp.get(k) or '—'}")
        print(f"   Members ({len(members)}):")
        for m in members:
            known = "; ".join(x for x in (m.get("known_for_1"), m.get("known_for_2"), m.get("known_for_3")) if x)
            drafted = f" → {m.get('class')} {m.get('power')} {m.get('ability')}" if m.get("ability") else ""
            print(f"     {m['card_id']} {m.get('name')}: wrote '{m.get('camp_raw')}'; known for: {known or '—'}{drafted}")
    loose = [c for c in wb.cards() if not wb.camp_for(c) and c.get("camp_raw") and c.get("camp_src") != "Ethos"]
    if loose:
        print("\nCampers whose camp isn't on the Camps tab: " +
              ", ".join(f"{c['card_id']} ('{c['camp_raw']}')" for c in loose))


def cmd_set_camp(a):
    wb = store.open_workbook()
    camp = wb.find_camp(a.name)
    if not camp:
        if not a.create:
            raise SystemExit(f"No camp '{a.name}'. Add --create to make it.")
        camp = wb.add_camp({"camp": a.name, "status": "new"})
    if wb.locked(camp) and not a.include_locked:
        raise SystemExit(f"{camp['camp']} is locked.")
    fields, skipped = {}, []
    for kv in a.fields:
        k, _, v = kv.partition("=")
        if k not in schema.CAMP_FIELDS:
            raise SystemExit(f"Unknown camp field '{k}'. Use one of: {', '.join(schema.CAMP_FIELDS)}")
        if camp.get(k) and not a.force and k not in ("status",):
            skipped.append(k)
            continue
        fields[k] = v
    if a.reviewed:
        fields["status"] = "ok"
    if fields:
        wb.update_camp(camp["camp"], fields)
    print(f"{camp['camp']}: set {', '.join(fields) or 'nothing'}"
          + (f"; kept your existing {', '.join(skipped)} (use --force to replace)" if skipped else ""))


# ---------------- drafting ----------------

def cmd_packet(a):
    from playacourt.generate import write_packet
    wb = store.open_workbook()
    warn_upgrade(wb)
    if not a.ids and not a.all:
        raise SystemExit("Name the cards (e.g. PC1-007), or --all for every unlocked submitted/drafting/review card.")
    cards = pick(wb.cards(), a.ids) if a.ids else [c for c in wb.cards() if c.get("status") in DRAFTABLE]
    for c in unlocked(wb, cards, a):
        print(write_packet(c, wb, a.note).as_posix())


def cmd_apply(a):
    from playacourt.generate import DRAFTS, apply_draft
    wb = store.open_workbook()
    bad = 0
    for c in pick(wb.cards(), a.ids):
        path = DRAFTS / f"{c['card_id']}.json"
        if not path.exists():
            print(f"✗ {c['card_id']}: no draft at {path.as_posix()}")
            bad += 1
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"✗ {c['card_id']}: draft is not valid JSON ({e})")
            bad += 1
            continue
        updates, errs, warns = apply_draft(c, wb, data)
        print(f"\n{c['card_id']} {c.get('name', '')}")
        for e in errs:
            print(f"  ✗ {e}")
        for w in warns:
            print(f"  ! {w}")
        if errs:
            bad += 1
            continue
        for k, v in updates.items():
            if str(c.get(k, "")) != str(v):
                print(f"  {schema.CARD_HEADER[k]}: {c.get(k, '') or '(blank)'}  →  {v}")
        if a.preview:
            print("  (preview only, nothing saved)")
            continue
        if c.get("status") == "submitted":
            updates["status"] = "drafting"
        updates["checks"] = "ok" if not warns else "; ".join(warns)
        updates["rules_hash"] = rules.rules_hash(dict(c, **updates))
        wb.update(c["card_id"], updates)
        print("  saved")
    return 1 if bad else 0


def cmd_check(a, wb=None):
    from playacourt.generate import camp_fixed
    wb = wb or store.open_workbook()
    bad = 0
    for c in pick(wb.cards(), getattr(a, "ids", None)):
        # Camp and badge follow the Camps tab unless you've claimed them (Camp: why).
        if not wb.locked(c) and c.get("camp_src", "") not in schema.OWNED_SOURCES and c.get("ability"):
            want = camp_fixed(c, wb)
            if want and any(c.get(k, "") != v for k, v in want.items()):
                print(f"  {c['card_id']}: camp/badge updated from the Camps tab → {want['camp'] or 'Rogue'} {want['badge']}")
                wb.update(c["card_id"], want)
        errs, warns = rules.check(c)
        summary = "ok" if not (errs or warns) else "; ".join([f"ERROR {x}" for x in errs] + warns)
        h = rules.rules_hash(c)
        if c.get("checks") != summary or c.get("rules_hash") != h:
            wb.update(c["card_id"], {"checks": summary, "rules_hash": h})
        flag = "✗" if errs else ("!" if warns else "✓")
        lock = " 🔒" if wb.locked(c) else ""
        print(f"{flag} {c['card_id']:8} {c.get('name', ''):18}{lock} {summary}")
        bad += bool(errs)
    for issue in rules.check_deck(wb.cards()):
        print(f"✗ deck: {issue}")
        bad += 1
    return 1 if bad else 0


def cmd_balance(a):
    from playacourt import balance
    wb = store.open_workbook()
    cards = [dict(c) for c in wb.cards()
             if c.get("status") not in ("withdrawn", "submitted")
             and (a.include_examples or c.get("status") != "example")
             and c.get("class") in rules.BEATS and str(c.get("power", "")).strip().isdigit()]
    balance.apply_overrides(cards, a.set)
    if len(cards) < 2:
        raise SystemExit("Need at least two playable cards (class + power) to test balance.")
    played, won = balance.simulate(cards, matches=a.matches)
    if a.set:
        print("What-if: " + ", ".join(a.set) + " (not saved)\n")
    print(balance.report(cards, played, won))


# ---------------- art and cards ----------------

def cmd_prompts(a):
    from playacourt import gapi
    wb = store.open_workbook()
    cards = [c for c in pick(wb.cards(), a.ids) if c.get("status") not in ("withdrawn", "example")
             and (a.all or c.get("art_status", "") in ("", "none", "prompt"))]
    cards = unlocked(wb, cards, a)
    if not cards:
        print("No cards need prompts (art already chosen?). Use --all to rebuild them anyway.")
        return
    for c in cards:
        fields = {"mj_prompt": art.build_prompt(c, wb.settings(), wb.camp_for(c))}
        if c.get("art_status", "") in ("", "none"):
            fields["art_status"] = "prompt"
        wb.update(c["card_id"], fields)
        print(f"{c['card_id']} {c.get('name', '')}:\n  {fields['mj_prompt']}\n")
    s = wb.settings()
    doc = gapi.write_doc(art.mj_queue_text(cards, wb.people()), s["drive_root_id"],
                         "Midjourney queue", s.get("mj_queue_doc_id") or None)
    if doc != s.get("mj_queue_doc_id"):
        wb.set_setting("mj_queue_doc_id", doc)
    print(f"Queue: https://docs.google.com/document/d/{doc}/edit")


def cmd_set_art(a):
    wb = store.open_workbook()
    card = pick(wb.cards(), [a.id])[0]
    if wb.locked(card) and not a.include_locked:
        raise SystemExit(f"{card['card_id']} is locked.")
    fid = art.set_art(wb, card, a.source, a.crop)
    print(f"{card['card_id']}: art set (Drive file {fid}). Run `python tools/pc.py refresh {card['card_id']}` to render.")


def cmd_gen_art(a):
    wb = store.open_workbook()
    for c in unlocked(wb, pick(wb.cards(), a.ids), a):
        wb.update(c["card_id"], {"art_status": "generating"})
        n = art.generate_gemini(c, wb.settings(), wb.people())
        wb.update(c["card_id"], {"art_status": "inbox"})
        print(f"{c['card_id']}: {n} image(s) in the Inbox")


def cmd_ingest_art(a, wb=None):
    wb = wb or store.open_workbook()
    done = art.ingest(wb, include_locked=a.include_locked)
    print(f"{len(done)} card(s) got new art." if done else "No new art in the Inbox (names must start with a card ID).")
    return done


def _render_to(wb, cards, out_dir, kinds):
    from playacourt import render
    arts = {c["card_id"]: art.download_art(c, out_dir) for c in cards}
    return render.render(cards, wb.settings(), out_dir, arts, kinds), arts


def cmd_render(a, wb=None):
    from playacourt import gapi
    wb = wb or store.open_workbook()
    s = wb.settings()
    cards = [c for c in pick(wb.cards(), a.ids) if c.get("status") not in ("withdrawn", "submitted")]
    cards = unlocked(wb, cards, a)
    todo = [c for c in cards if a.force or rules.needs_render(c) or not c.get("print_file_id")]
    if not todo:
        print("Nothing to render: every card matches its last render (use --force to redo).")
        return
    with tempfile.TemporaryDirectory() as tmp:
        outs, arts = _render_to(wb, todo, Path(tmp), tuple(KIND_FIELD))
        for c in todo:
            label = f"{c['card_id']} {c.get('name', '')}".strip()
            ids = {}
            for kind, path in outs[c["card_id"]].items():
                field, folder_key, desc = KIND_FIELD[kind]
                if not s.get(folder_key):
                    print(f"  ! no Drive folder for {desc} (run upgrade-sheet); kept local only")
                    continue
                if c.get(field):
                    gapi.replace_content(c[field], path)
                    ids[field] = c[field]
                else:
                    ids[field] = gapi.upload(path, s[folder_key], f"{label} ({desc}).png")
            wb.update(c["card_id"], {**ids, "rendered_hash": rules.rules_hash(c), "rules_hash": rules.rules_hash(c)})
            print(f"  rendered {label}{'' if arts[c['card_id']] else ' (no art yet)'}")


def cmd_refresh(a):
    wb = store.open_workbook()
    print("1/3 Collecting new art from the Inbox")
    cmd_ingest_art(a, wb)
    print("2/3 Checking cards")
    cmd_check(a, wb)
    print("3/3 Rendering changed cards")
    cmd_render(a, wb)


def cmd_export(a):
    wb = store.open_workbook()
    kinds = tuple(KIND_FIELD) if "all" in a.kind else tuple(dict.fromkeys(a.kind))
    out = Path(a.to).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    cards = pick(wb.cards(), a.ids)
    with tempfile.TemporaryDirectory() as tmp:
        outs, _ = _render_to(wb, cards, Path(tmp), kinds)
        for c in cards:
            for kind, path in outs[c["card_id"]].items():
                name = f"{c['card_id']}-{c.get('name', '').replace(' ', '-')}-{kind}.png"
                shutil.copyfile(path, out / name)
                print((out / name).as_posix())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, hlp, ids=True, lock=True):
        p = sub.add_parser(name, help=hlp)
        if ids:
            p.add_argument("ids", nargs="*", help="card IDs (default: all)")
        if lock:
            p.add_argument("--include-locked", action="store_true", help="also touch Locked cards/camps")
        p.set_defaults(fn=fn)
        return p

    cmd("upgrade-sheet", cmd_upgrade_sheet, "add missing tabs/columns/settings/folders", ids=False, lock=False)
    p = cmd("intake", cmd_intake, "copy new sign-up responses into the sheet", ids=False, lock=False)
    p.add_argument("--dry-run", action="store_true", help="show what would be added")
    p = cmd("camps", cmd_camps, "show camps and members", ids=False, lock=False)
    p.add_argument("--new", action="store_true", help="only camps with Status = new")
    p = sub.add_parser("set-camp", help="fill in a camp's details")
    p.add_argument("name")
    p.add_argument("fields", nargs="*", metavar="field=value")
    p.add_argument("--force", action="store_true", help="replace fields that already have a value")
    p.add_argument("--create", action="store_true", help="add the camp if it doesn't exist")
    p.add_argument("--reviewed", action="store_true", help="mark Status = ok")
    p.add_argument("--include-locked", action="store_true")
    p.set_defaults(fn=cmd_set_camp)

    p = cmd("packet", cmd_packet, "write drafting packets for Claude Code")
    p.add_argument("--all", action="store_true", help="every unlocked submitted/drafting/review card")
    p.add_argument("--note", metavar="TEXT", help="one-off instruction for this packet only")
    p = cmd("apply", cmd_apply, "validate and save drafts from private/work/drafts", lock=False)
    p.add_argument("--preview", action="store_true", help="show the changes without saving")
    cmd("check", cmd_check, "validate cards against the ethos", lock=False)
    p = cmd("balance", cmd_balance, "Monte Carlo balance test", ids=False, lock=False)
    p.add_argument("--set", action="append", metavar="ID.field=value", help="what-if override (repeatable)")
    p.add_argument("--matches", type=int, default=20000)
    p.add_argument("--include-examples", action="store_true", help="include the PC0 example cards")

    p = cmd("prompts", cmd_prompts, "build Midjourney prompts → sheet + Google Doc")
    p.add_argument("--all", action="store_true", help="also cards whose art is already chosen")
    p = sub.add_parser("set-art", help="use an image (local file or Drive ID) as a card's art")
    p.add_argument("id")
    p.add_argument("source", help="local image path, or Drive file ID/link")
    p.add_argument("--crop", help='which part to keep, e.g. "50%% 30%%"')
    p.add_argument("--include-locked", action="store_true")
    p.set_defaults(fn=cmd_set_art)
    cmd("gen-art", cmd_gen_art, "generate art with Gemini (optional, paid)")
    cmd("ingest-art", cmd_ingest_art, "Inbox → Chosen", ids=False)
    p = cmd("render", cmd_render, "render print/no-bleed/display PNGs → Drive")
    p.add_argument("--force", action="store_true", help="re-render even if unchanged")
    p = cmd("refresh", cmd_refresh, "ingest-art + check + render")
    p.add_argument("--force", action="store_true", help="re-render even if unchanged")
    p = cmd("export", cmd_export, "save local PNG copies", lock=False)
    p.add_argument("--kind", nargs="+", choices=["bleed", "trim", "display", "all"], default=["all"])
    p.add_argument("--to", default=str(Path.home() / "Downloads" / "playacourt-cards"))

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
