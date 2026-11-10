#!/usr/bin/env python3
"""Playa Court card pipeline. All card data lives in Google Drive (PlayaCourt folder).

  check                   validate every card against the ethos, record results in the sheet
  generate IDS | --all    draft rules with Claude (only fields you haven't claimed; skips Locked)
                          --note TEXT one-off instruction, --dry-run show request, --preview don't save
  balance [--set ...]     Monte Carlo balance test, with what-if overrides
  prompts [IDS]           build Midjourney prompts (sheet + Google Doc queue)
  gen-art IDS             generate art with Gemini (optional, paid)
  ingest-art              Inbox → Chosen for each card with a new image
  render [IDS]            render print + display PNGs for changed cards → Drive
  refresh [IDS]           ingest-art + check + render: drop new art in the Inbox, run this

Locked cards (Locked = yes) are skipped by generate, prompts, ingest-art and render unless
you pass --include-locked. See tools/README.md.
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playacourt import art, rules, schema, store  # noqa: E402

DRAFTABLE = {"submitted", "drafting", "review"}


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


def cmd_check(a, wb=None):
    wb = wb or store.open_workbook()
    bad = 0
    for c in pick(wb.cards(), getattr(a, "ids", None)):
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


def cmd_generate(a):
    from playacourt.generate import build_request, generate_card
    wb = store.open_workbook()
    if not a.ids and not a.all:
        raise SystemExit("Name the cards to generate (e.g. PC1-007 PC1-008), or --all for every "
                         "unlocked submitted/drafting/review card. Each card is one billed Claude call.")
    cards = pick(wb.cards(), a.ids) if a.ids else [c for c in wb.cards() if c.get("status") in DRAFTABLE]
    cards = unlocked(wb, cards, a)
    if a.dry_run:
        for c in cards:
            print(f"===== {c['card_id']} {c.get('name', '')}: request that would be sent (nothing sent) =====")
            print(build_request(c, wb, a.note))
        return
    verb = "Previewing (not saved)" if a.preview else "Generating"
    print(f"{verb} {len(cards)} card(s) with {wb.settings().get('gen_model')}...")
    for c in cards:
        try:
            updates = generate_card(c, wb, note=a.note)
        except RuntimeError as e:
            print(f"  x {e}")
            continue
        if a.preview:
            print(f"  {c['card_id']} {c.get('name', '')} would change:")
            for k, v in updates.items():
                if str(c.get(k, "")) != str(v):
                    print(f"    {schema.CARD_HEADER[k]}: {c.get(k, '') or '(blank)'}  ->  {v}")
            continue
        if c.get("status") == "submitted":
            updates["status"] = "drafting"
        wb.update(c["card_id"], updates)
        print(f"  ok {c['card_id']} {c.get('name', '')}: {c.get('class')} {c.get('power')} | {c.get('ability')}")
    if not a.preview:
        cmd_check(argparse.Namespace(ids=[c["card_id"] for c in cards]), wb)


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
        fields = {"mj_prompt": art.build_prompt(c, wb.settings())}
        if c.get("art_status", "") in ("", "none"):
            fields["art_status"] = "prompt"
        wb.update(c["card_id"], fields)
    s = wb.settings()
    doc = gapi.write_doc(art.mj_queue_text(cards, wb.people()), s["drive_root_id"],
                         "Midjourney queue", s.get("mj_queue_doc_id") or None)
    if doc != s.get("mj_queue_doc_id"):
        wb.set_setting("mj_queue_doc_id", doc)
    print(f"{len(cards)} prompt(s) → https://docs.google.com/document/d/{doc}/edit")


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


def cmd_render(a, wb=None):
    from playacourt import gapi, render
    wb = wb or store.open_workbook()
    s = wb.settings()
    cards = [c for c in pick(wb.cards(), a.ids) if c.get("status") not in ("withdrawn", "submitted")]
    cards = unlocked(wb, cards, a)
    todo = [c for c in cards if a.force or rules.needs_render(c) or not c.get("print_file_id")]
    if not todo:
        print("Nothing to render: every card matches its last render (use --force to redo).")
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        arts = {c["card_id"]: art.download_art(c, tmp) for c in todo}
        outs = render.render(todo, s, tmp, arts)
        for c in todo:
            pr, dp = outs[c["card_id"]]
            label = f"{c['card_id']} {c.get('name', '')}".strip()
            ids = {}
            for key, path, folder, kind in (("print_file_id", pr, s["drive_print_id"], "print"),
                                            ("display_file_id", dp, s["drive_display_id"], "display")):
                if c.get(key):
                    gapi.replace_content(c[key], path)
                    ids[key] = c[key]
                else:
                    ids[key] = gapi.upload(path, folder, f"{label} ({kind}).png")
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


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, hlp, ids=True, lock=True):
        p = sub.add_parser(name, help=hlp)
        if ids:
            p.add_argument("ids", nargs="*", help="card IDs (default: all)")
        if lock:
            p.add_argument("--include-locked", action="store_true", help="also touch Locked cards")
        p.set_defaults(fn=fn)
        return p

    cmd("check", cmd_check, "validate cards against the ethos", lock=False)
    p = cmd("generate", cmd_generate, "draft rules with Claude for the named cards")
    p.add_argument("--all", action="store_true", help="every unlocked submitted/drafting/review card")
    p.add_argument("--note", metavar="TEXT", help="one-off instruction for this run only (not saved)")
    p.add_argument("--dry-run", action="store_true", help="print the exact request; don't call Claude")
    p.add_argument("--preview", action="store_true", help="call Claude and show the draft; don't save it")
    p = cmd("balance", cmd_balance, "Monte Carlo balance test", ids=False, lock=False)
    p.add_argument("--set", action="append", metavar="ID.field=value", help="what-if override (repeatable)")
    p.add_argument("--matches", type=int, default=20000)
    p.add_argument("--include-examples", action="store_true", help="include the PC0 example cards")
    p = cmd("prompts", cmd_prompts, "build Midjourney prompts → sheet + Google Doc")
    p.add_argument("--all", action="store_true", help="also cards whose art is already chosen")
    cmd("gen-art", cmd_gen_art, "generate art with Gemini (paid)")
    cmd("ingest-art", cmd_ingest_art, "Inbox → Chosen", ids=False)
    p = cmd("render", cmd_render, "render print + display PNGs → Drive")
    p.add_argument("--force", action="store_true", help="re-render even if unchanged")
    p = cmd("refresh", cmd_refresh, "ingest-art + check + render")
    p.add_argument("--force", action="store_true", help="re-render even if unchanged")

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
