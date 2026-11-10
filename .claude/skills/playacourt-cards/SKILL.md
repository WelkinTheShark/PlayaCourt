---
name: playacourt-cards
description: Process Playa Court card submissions end to end. Pull new sign-ups into the Drive sheet, coordinate camps, design each card's rules and art direction, write Midjourney prompts, set art, and render/export finished cards. Use when the user says "process new submissions", "draft cards", "design PC1-007", "update a card's art", "export cards", or runs /playacourt-cards.
---

# Playa Court card studio

You (Claude Code) are the card designer. The scripts in `tools/pc.py` only move data between
the Google Sheet "Playa Court Cards" (Drive → PlayaCourt) and work files. **Never call an LLM API**;
you do the creative work yourself in this session.

Run everything from the repo root: `python tools/pc.py <command>`. Work files live in
`private/work/` (gitignored). Never copy anything from `private/` or the People tab into a
commit, a chat summary for others, or an art prompt.

## Ground rules

- **The rulebook is the Ability ethos** (Google Doc in PlayaCourt). Every packet includes the
  current text. Follow it exactly; where a guideline conflicts with it, follow the ethos and say so
  in `notes`.
- **Locked = yes** on a card or a camp: don't draft it, don't change it, and say it was skipped.
- **FIXED fields** in a packet were chosen by the designer (why = Form/Known/Balance/Ethos, or
  set by the Camps tab). Return them unchanged.
- **Guideline precedence:** later lines in a packet's Guidelines section win, so the card's own
  guidelines beat camp rules, which beat class/tag rules, which beat "All cards".
- **Show before saving:** always run `apply --preview` and show the user the diff before `apply`.
- **Privacy:** packets never contain contact details. Don't go looking for them. Photo consent is
  only checked by the scripts when building the Midjourney queue.

## The workflow

### 1. Intake new submissions
```
python tools/pc.py upgrade-sheet        # first time, or after the tools are updated
python tools/pc.py intake --dry-run     # check the column mapping
python tools/pc.py intake
```
Show the user what was added: new cards, new camps, and the Rogues (answers that aren't a real
camp). If the column mapping looks wrong (e.g. a question landed in the wrong field), stop and
tell the user which `FORM_MAP` phrase to adjust in `tools/playacourt/schema.py`.

### 2. Coordinate camps
```
python tools/pc.py camps --new
```
For each new camp, and for any camp whose members don't fit its profile yet:

- **Merge duplicates.** If two camp rows are the same camp spelled differently, keep the clearer
  name and add the other as an alias: `set-camp "The Fire Circle" aliases="Fire Circle, firecircle"`.
  Tell the user so they can delete the duplicate row.
- **Rogue check (ethos §2).** Staff, volunteer, crew areas, own names, "none" and "wherever" are not
  camps: `set-camp "Staff camping" rogue=yes`.
- **Propose a profile from the members' answers and the camp name:**
  - `badge`: 2–3 capital letters, distinct from the other camps' badges.
  - `theme`: one sentence on what the camp is about.
  - `rule_themes`: which tags and mechanics members' abilities should lean on, e.g.
    "[Food] synergy; reward having other [Food] allies". Base it on the ethos tag table.
  - `art_setting`: the shared scene, e.g. "inside a lantern-lit snack shack at night".
  - `art_motifs`: recurring props, symbols and colours.
- Show the proposals as a short table, then write them on the user's OK:
  `python tools/pc.py set-camp "NAME" badge=XX theme="…" rule_themes="…" art_setting="…" art_motifs="…" --reviewed`
  `set-camp` only fills blank fields, so it won't overwrite what the user typed. Use `--force` only
  when the user asks.

### 3. Draft the rules for each card
```
python tools/pc.py packet PC1-007 PC1-008      # or --all; --note "…" for a one-off instruction
```
Read each packet (`private/work/packets/<ID>.md`) in full, then design the card.

**Design process, in this order:**
1. **Tags (ethos §9):**
   - Use one or two tags, each traceable to a named source: the "known for" answers first
     (most concrete first), then the camp's purpose.
   - Literal beats inferred. Feelings and skills are not tags.
2. **Class:**
   - Start from "Class they picked", unless a FIXED class or a guideline overrides it.
   - Check the fit against the class roles in ethos §3.
3. **Camp coordination:**
   - Read the camp's theme and rule themes, and the other members already drafted.
   - The ability should feel like this camp (e.g. Fire Circle members reward [Fire]), but
     **don't clone**: vary the class role, scope/timing and the specific mechanic between campmates.
   - Make campmates combo with each other where it fits naturally.
4. **Ability (ethos §1, §4–7):**
   - One ability of at most 135 characters, phrased as plus rather than minus.
   - Size it to the class (§4); Jokers stay at power 1–5 with a single condition.
   - Use multiplayer-safe wording ("any camp", "enemy").
   - Use the Self:/Aura: scope labels and the timing labels exactly as the ethos defines them.
   - Leave out "card" after a tag.
5. **Power:** balance power against the ability size and the deck summary in the packet. A bigger
   ability means a lower power.
6. **Fit to the person (§8):**
   - The ability and flavour should read like what they're known for and what the designer wrote
     in "What I know about them".
   - Flavour text is one short line, PG-13, and never mean.
7. **Rarity:** Uncommon unless a guideline says otherwise.
8. **ability_value:** your honest estimate of the average power the ability adds in a typical
   round, used by the balance test. A conditional bonus is weighted by how often its condition
   fires.
9. **art_brief:** one sentence covering who, doing what, where. No style words; the camp setting
   and house style are added automatically.
10. **notes:** two or three sentences on the tag sources, the class choice, how it coordinates with
    the camp, and what you balanced against.

**Self-check before writing the draft:**
- Every tag has a source.
- FIXED fields are unchanged.
- The ability is at most 135 characters.
- The ability doesn't duplicate an existing deck ability.
- The wording isn't for two players only.
- No minus on a non-Queen/Joker.
- Every guideline has been followed, or the conflict is explained in notes.

Write the draft to `private/work/drafts/<ID>.json`, one JSON object with exactly the schema keys,
then:
```
python tools/pc.py apply PC1-007 --preview
```
Show the user the diff and any warnings. Fix any errors and preview again. On the user's OK:
```
python tools/pc.py apply PC1-007
```
**Redrafting:** the user can change Card guidelines, What I know about them, Art notes, the camp,
or the Guidelines tab, then ask again. Regenerate the packet, because it's rebuilt from the
sheet, and redraft. Fields the user has since claimed (why = Known/Balance) now show up as FIXED.

### 4. Balance
```
python tools/pc.py balance
python tools/pc.py balance --set PC1-007.power=5 --set PC1-007.ability_value=1.5
```
Point out cards flagged strong or weak, and suggest specific fixes, testing them with `--set`
what-ifs first. Remember it's a smoke test: it reads power and ability_value, not the ability
wording.

### 5. Art direction (Midjourney)
```
python tools/pc.py prompts PC1-007
```
The prompt is built from these parts, in order:
1. the art brief;
2. the camper's Art notes;
3. the camp's Art setting and motifs;
4. the class colour;
5. the house Art style;
6. the Midjourney parameters.

If the prompt reads badly, fix the *source* cell (Art brief / Art notes / camp art fields), not the
prompt itself, then run `prompts PC1-007 --all` to rebuild it. Then tell the user how to use it:
- Run the prompts in Midjourney; they're also in the "Midjourney queue" Doc.
- Attach the person's photo as `--oref` only where the queue says consent is yes.
- Save the chosen image to PlayaCourt / 2 - Card Art / Inbox, with a name starting with the card ID.

**Midjourney has no API and automating it breaks its terms: never try to drive it.**

### 6. Set or replace art
Either way, there's no Photoshop step: the card is composed from the sheet values and the art.
- From the Inbox: `python tools/pc.py refresh PC1-007` picks up the newest `PC1-007…` image.
- From a file the user gives you: `python tools/pc.py set-art PC1-007 "C:/path/art.png" --crop "50% 30%"`.
- Framing: change the crop (Art crop column, or `--crop`) and refresh again. The first number moves
  the view left/right and the second up/down.

### 7. Render and export
```
python tools/pc.py refresh [IDS]                    # render changed cards to Drive (3 versions)
python tools/pc.py export PC1-007 --kind all --to "C:/Users/<you>/Downloads/cards"
```
| Version | Size | Use |
|---|---|---|
| `bleed` | 2.75×3.75 in, 1650×2250 | Print shop file. Colour runs 0.125 in past the cut line. |
| `trim` | 2.5×3.5 in, 1500×2100, square corners | Print without bleed: home printing, or shops that add their own bleed. |
| `display` | 1500×2100, rounded corners, transparent | Screens and the website. |

After rendering, offer to look at the display PNG with the user, to check the art crop and text fit.

### 8. Finalise
When the user is happy with a card, suggest setting **Status = approved** and **Locked = yes** in
the sheet. Locked cards are then left alone by everything above.

## Quick reference
| User says | Do |
|---|---|
| "process new submissions" | Steps 1–3 for the new cards, then 4–5 |
| "make the Fire Circle more fire-themed" | `set-camp "The Fire Circle" rule_themes="…" --force` (with OK), then redraft its unlocked members |
| "redo PC1-007 but more of a combo piece" | `packet PC1-007 --note "make it a combo piece"`, then draft, preview, apply |
| "new art for Zaddy" | Step 6 |
| "export Wob for print" | `export PC1-006 --kind bleed trim` |
| "is the deck balanced?" | Step 4 |
