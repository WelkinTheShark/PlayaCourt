# Playa Court card pipeline

All card data lives in **Google Drive → PlayaCourt**, never in this public repo:

```
PlayaCourt/
  Playa Court Cards            ← the sheet: Cards, Guidelines, People (private), Settings, Lists
  Ability ethos (card design rules)  ← the rulebook `check` follows and `generate` reads
  READ ME - how the card files work
  Midjourney queue             ← created by `prompts`
  1 - Reference Photos (private)
  2 - Card Art/
      Inbox - drop new art here (name starts with card ID)
      Chosen - final art per card
  3 - Finished Cards (rendered PNGs)/
      Print (with bleed)
      Display (trimmed)
```

This folder holds only code. Locally, `private/` (gitignored) holds your Google credentials and
`config.toml` with the sheet ID. While rendering, the scripts use temp files that are deleted
afterwards.

## Fast changes

| You want to… | Do this |
|---|---|
| Swap a card's art | Save the image to *2 - Card Art / Inbox* named `PC1-005-anything.png`, then `python tools/pc.py refresh` |
| Change rules or text | Edit the row in the sheet, then `python tools/pc.py refresh`. Only changed cards re-render. |
| Draft rules with AI | Add guidelines, then `python tools/pc.py generate PC1-007` |
| Theme a camp | On the **Guidelines** tab: *Applies to* = Camp, *Which* = the camp name, *Active* = yes. Then `generate` its cards. |
| Balance test | `python tools/pc.py balance`. To try a change without saving it: `--set PC1-002.power=6` |
| Freeze a finished card | Set **Locked** = yes |

## How regeneration stays safe

- **Locked = yes**: `generate`, `prompts`, `ingest-art` and `render` all skip the card. New art
  for a locked card stays in the Inbox. Add `--include-locked` to override.
- **The "why" columns**:
  - A field marked **Form**, **Known**, **Balance** or **Ethos** is yours. `generate` passes it
    to the model as fixed and never changes it, even when it's blank (e.g. no camp = Rogue).
  - Fields that are empty or marked **AI draft** / **Placeholder** are regenerated.
  - To keep an AI suggestion, change its why to Known or Balance.
- **Re-rendering only when needed**:
  - Every card has a hash of everything printed on it.
  - `render` and `refresh` redraw a card only when that hash changed. A card with no finished
    file yet is always drawn.
  - Re-rendering overwrites the existing Drive files, so their links stay the same.

## Guidelines for AI rule drafting

`generate` sends Claude:
- the whole of the **Ability ethos** Google Doc in PlayaCourt, read fresh each run (its ID is
  `ethos_doc_id` in `private/config.toml`);
- a one-line summary of every other card, for balance;
- the sign-up answers;
- the fixed fields;
- every guideline that applies to the card:
  - **Guidelines tab** rows with *Active* = yes, matched by All cards, Camp (printed or as
    written on the form), Class, Tag or Card ID;
  - the card's own **Card guidelines** column.

It returns:
- class, camp/badge, power, tags, scope/timing, ability, flavour, rarity;
- an **ability value** estimate (used by the balance test);
- an **art brief**;
- a short **AI notes** explanation.

The model is set in *Settings → Rules model*; the default is `claude-opus-5-5`. Each card is one
billed API call.
- **Refusals:** the call uses the API's server-side refusal fallback. If the model declines,
  the request is retried on a fallback model instead of failing.
- **Credentials:** uses `ANTHROPIC_API_KEY`, or a profile from `ant auth login`.

## Print and display renders

| | Size at 600 dpi | Notes |
|---|---|---|
| Print | 1650 × 2250 (2.75 × 3.75 in) | Card plus bleed (default 0.125 in, *Settings → Print bleed*) on every side. Band and background run past the cut line; square corners. |
| Display | 1500 × 2100 (2.5 × 3.5 in) | Trimmed card, rounded corners, transparent outside. |

The layout matches the existing PC1 cards. It uses the same positions as the site's card CSS,
class element symbols on the power gem and the Beats line, and Self/Aura labels in the class
colour. The template is `playacourt/card.html`. After you change it, bump `TEMPLATE_VERSION` in
`rules.py` so every card re-renders.

## Art

- **Midjourney**:
  - It has no official API, and automating it breaks its terms. `prompts` writes a paste-ready
    queue to the *Midjourney queue* Doc instead.
  - You run the prompts and save your pick to the Inbox.
  - Attach a person's photo as a reference (`--oref`) only if the People tab says yes.
- **Gemini**: `gen-art --provider gemini` uploads straight to the Inbox. It needs `[gemini]
  api_key` in `private/config.toml` (paid) and hasn't been run yet.
- House style comes from *Settings*: Art style, Midjourney parameters and Midjourney style
  reference. Per card, edit the **Art brief**.

## Balance test

`balance` plays 20,000 random best-of-5 matches:
- The class ring decides each round first, then power + *Ability value (est.)*.
- It reports win rates per card and per class, and flags anything above 58% or below 42%.

It doesn't read ability wording, so it's a quick smoke test, not a proof. Fill in the ability
values (by hand or with `generate`) to make it more meaningful.

## Setup (once)

1. `pip install -r tools/requirements.txt`, then `playwright install chromium`, or use the
   installed Chrome.
2. Google Cloud Console:
   - Enable the **Google Sheets API** and the **Google Drive API**.
   - Create an **OAuth client ID** (*Desktop app*) and save it as
     `private/secrets/client_secret.json`.
   - Add yourself as a test user on the consent screen.
3. `private/config.toml` already points at the sheet. The first command opens a browser to sign
   in, and the token is saved in `private/secrets/`.
4. For `generate`: set `ANTHROPIC_API_KEY`, or run `ant auth login`.

## Files

| Path | Contents |
|---|---|
| `pc.py` | Command-line entry point. `python tools/pc.py -h` lists the commands. |
| `playacourt/schema.py` | Sheet tabs, columns (readable headers ↔ code keys), dropdowns, settings. |
| `playacourt/store.py` | Reads and writes the sheet; guideline matching; Locked. |
| `playacourt/rules.py` | Class ring, colours, symbols, ethos checks, card hashes. |
| `playacourt/generate.py` | AI rule drafting. |
| `playacourt/balance.py` | Monte Carlo balance test. |
| `playacourt/art.py` | Prompts, Midjourney queue, Gemini adapter, Inbox → Chosen. |
| `playacourt/render.py`, `card.html` | Card template and the print/display renderer. |
| `playacourt/gapi.py` | Google auth, Sheets and Drive helpers. |
