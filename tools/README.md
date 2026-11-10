# Playa Court card studio

Card data lives in **Google Drive → PlayaCourt**. Cards are designed by **Claude Code** following
`.claude/skills/playacourt-cards/SKILL.md`; there are no paid AI API calls. These scripts move data
between the sheet, Drive and Claude Code, and render the finished cards.

```
PlayaCourt/
  Playa Court Cards                  ← the processing sheet (tabs below)
  Ability ethos (card design rules)  ← the rulebook; every drafting packet includes it
  READ ME - how the card files work
  Midjourney queue                   ← created by `prompts`
  1 - Reference Photos (private)
  2 - Card Art/  Inbox - drop new art here · Chosen - final art per card
  3 - Finished Cards/  Print (with bleed) · Print (no bleed) · Display (trimmed)
```

## In Claude Code

Open this repo in Claude Code and say **"process new submissions"** (or `/playacourt-cards`).
The skill walks through:
1. intake
2. coordinating camps
3. drafting each card (you approve every change)
4. balance
5. Midjourney prompts
6. art
7. render and export

You can also ask for a single step: "redo PC1-007 as more of a combo piece", "make the Fire
Circle more fire-themed", "new art for Zaddy", "export Wob for print".

## The processing sheet

| Tab | What you put there |
|---|---|
| **Cards** | One row per camper. Your custom info for that camper goes in three columns: **What I know about them**, **Card guidelines** (instructions for their rules), and **Art notes** (art direction). |
| **Camps** | One row per camp, used to coordinate every member's card: **Badge**, **Not a real camp?** (Rogue), **Camp theme**, **Rule themes** (tags or mechanics members lean on), **Art setting** and **Art motifs & colours** (shared in every member's art), **Aliases** (other spellings people used). |
| **Guidelines** | Rules for many cards at once: All cards / Camp / Class / Tag / Card ID, switched on with *Active = yes*. |
| **People (private)** | Contact details, photo link and photo consent. Filled in by intake; never put into drafting packets. |
| **Settings** | Event line, set code, art style, Midjourney parameters, print bleed, Form responses sheet, folder links. |

**What steers a card** (the packet lists these; later lines win):
1. All-cards guidelines;
2. class and tag guidelines;
3. camp guidelines, then the camp's theme and rule themes;
4. the card's own guidelines;
5. any one-off `--note`.

**Keeping your choices:**
- **Fields you claim are never redrafted:**
  - A field whose "why" is **Form**, **Known**, **Balance** or **Ethos** stays fixed, even when blank.
  - Fields marked **AI draft** or **Placeholder**, or left blank, can be redrafted.
- **Camp and badge** always follow the Camps tab: change a camp's badge and the next `check` or
  `refresh` updates every member. The exception is a card whose *Camp: why* you've set.
- **Locked = yes** on a card or camp freezes it.

## Commands

Run from the repo root: `python tools/pc.py <command>`. `-h` on any command shows its options.

| Step | Command |
|---|---|
| Set up / update the sheet | `upgrade-sheet` (adds missing tabs, columns, settings, folders; safe to re-run) |
| Pull new sign-ups | `intake --dry-run`, then `intake` |
| Review camps | `camps --new` |
| Fill in a camp | `set-camp "Name" badge=FC theme="…" rule_themes="…" art_setting="…" art_motifs="…" --reviewed`. Only blank fields are filled; `--force` replaces existing ones. |
| Drafting packet for Claude Code | `packet PC1-007 [--note "…"]` writes `private/work/packets/PC1-007.md` |
| Save Claude Code's draft | `apply PC1-007 --preview`, then `apply PC1-007` (reads `private/work/drafts/PC1-007.json`) |
| Ethos checks | `check` |
| Balance test | `balance`, plus what-ifs: `--set PC1-007.power=6` |
| Midjourney prompts | `prompts PC1-007` (sheet + "Midjourney queue" Doc) |
| Use an image as the art | `set-art PC1-007 path/to/art.png --crop "50% 30%"`, or drop it in the Inbox named `PC1-007-…` |
| Render changed cards → Drive | `refresh` (= ingest-art + check + render) |
| Save local copies | `export PC1-007 --kind bleed trim display --to <folder>` |

## Card versions

| Version | Size at 600 dpi | For |
|---|---|---|
| `bleed` | 1650 × 2250 (2.75 × 3.75 in) | Print shops. Colour runs 0.125 in past the cut line (*Settings → Print bleed*). |
| `trim` | 1500 × 2100 (2.5 × 3.5 in), square corners | Printing without bleed: home printing, or shops that add their own. |
| `display` | 1500 × 2100, rounded corners, transparent | Screens and the website. |

Art and sheet values are composed into the card template automatically, with no Photoshop step.
The **Art crop** column (or `set-art --crop`) frames the image.

## Art prompts

`prompts` builds each Midjourney prompt from these parts, in order:
1. the card's **Art brief** (written in the draft);
2. the camper's **Art notes**;
3. the camp's **Art setting** and **Art motifs**;
4. the class colour;
5. the house **Art style**;
6. the Midjourney parameters and style reference.

To change the result, edit those cells rather than the prompt. Midjourney has no API and
automating it breaks its terms, so you run the prompts yourself and save the pick to the Inbox.
Attach a reference photo only where the queue says consent is yes.

## Setup (once)

1. `pip install -r tools/requirements.txt`, then `playwright install chromium`, or use the
   installed Chrome.
2. Google Cloud Console (free):
   - Enable the **Google Sheets API** and the **Google Drive API**.
   - Create an **OAuth client ID** of type *Desktop app* and save it as
     `private/secrets/client_secret.json`.
   - Add yourself as a test user on the consent screen.
3. `private/config.toml` holds `spreadsheet_id` and `ethos_doc_id` (already filled in). The first
   command opens a browser to sign in, and the token is saved in `private/secrets/`.
4. In the sign-up Form: **Responses → Link to Sheets**. Share that Sheet with the PlayaCourt Drive
   account, then put its ID in *Settings → Form responses sheet*.
5. `python tools/pc.py upgrade-sheet`.

## Files

| Path | Contents |
|---|---|
| `pc.py` | Command-line entry point. |
| `playacourt/schema.py` | Tabs, columns (readable headers ↔ code keys), form mapping (`FORM_MAP`), settings. |
| `playacourt/store.py` | Reads and writes the sheet; camp matching (names and aliases); guidelines; Locked. |
| `playacourt/intake.py` | Form responses → Cards / People / Camps. |
| `playacourt/generate.py` | Drafting packets for Claude Code; draft validation and apply. |
| `playacourt/rules.py` | Class ring, colours, symbols, ethos checks, card hashes. |
| `playacourt/balance.py` | Monte Carlo balance test. |
| `playacourt/art.py` | Prompt building, Midjourney queue, `set-art`, Inbox → Chosen, optional Gemini. |
| `playacourt/render.py`, `card.html` | Card template; bleed / trim / display rendering. Bump `TEMPLATE_VERSION` in `rules.py` after editing the template. |
| `playacourt/gapi.py` | Google auth, Sheets and Drive helpers. |
| `../.claude/skills/playacourt-cards/SKILL.md` | The design rules and workflow Claude Code follows. |
