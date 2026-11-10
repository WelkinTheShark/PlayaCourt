"""The card workbook's shape: tabs, columns and allowed values.

All card data lives in Google Drive (PlayaCourt/Playa Court Cards). Nothing about cards is
stored in this public repo. Column headers in the sheet are plain English; the scripts map
them to the short keys used in code via the tables below.
"""

CLASSES = ["King", "Queen", "Knight", "Page", "Joker"]
TAGS = ["Food", "Sound", "Dance", "Fire", "Glow", "Art", "Build", "Care", "Crew", "Night", "Vehicle"]
SCOPES = ["", "Self", "Aura"]
TIMINGS = ["", "This round", "If this wins", "If this loses"]
RARITIES = ["Common", "Uncommon", "Rare"]
ELEMENTS = ["", "Fire", "Water", "Air", "Earth"]

# Where a design decision came from ("… why" columns).
SOURCES = [
    "Form",         # straight from the person's sign-up answers
    "Known",        # chosen from knowing the person
    "Balance",      # chosen or adjusted for game balance
    "Ethos",        # applied from ability-ethos rules (e.g. staff camp → Rogue)
    "AI draft",     # written by `generate`; regenerated freely until you change the why
    "Placeholder",  # stand-in; must be replaced before the card is approved
]

STATUSES = ["submitted", "drafting", "review", "approved", "printed", "withdrawn", "example"]
PUBLISHED_STATUSES = {"approved", "printed", "example"}
ART_STATUSES = ["none", "prompt", "generating", "inbox", "chosen"]

TAB_CARDS, TAB_PEOPLE, TAB_SETTINGS, TAB_LISTS = "Cards", "People (private)", "Settings", "Lists"
TAB_GUIDELINES = "Guidelines"
YES = {"yes", "y", "true", "x", "1"}

# A field counts as yours (never regenerated) when its "why" is one of these.
OWNED_SOURCES = {"Form", "Known", "Balance", "Ethos"}

# (key used in code, sheet header, note on the header cell)
CARD_COLUMNS = [
    # --- Card ---
    ("card_id", "Card ID", "Set code + number, e.g. PC1-007. Never reuse an ID."),
    ("status", "Status", "submitted → drafting → review → approved → printed (or withdrawn)."),
    ("locked", "Locked", "yes = finalized. generate / prompts / render all leave this card alone."),
    ("name", "Name", "Name or playa name as printed on the card."),
    # --- From the sign-up form ---
    ("class_requested", "Class they picked", "Class chosen on the sign-up form."),
    ("camp_raw", "Camp they wrote", "Camp exactly as written on the form."),
    ("known_for_1", "Known for 1", "From the form."),
    ("known_for_2", "Known for 2", "From the form."),
    ("known_for_3", "Known for 3", "From the form."),
    ("my_input", "What I know about them", "Your own knowledge of the person that shaped the card."),
    ("guidelines", "Card guidelines", "Instructions for generating this card's rules, e.g. 'make it a combo piece with [Fire]'."),
    # --- Card design (each with a 'why') ---
    ("class", "Class", ""), ("class_src", "Class: why", "Form / Known / Balance / Ethos / Placeholder"),
    ("camp", "Camp", "Printed camp. Leave blank for a Rogue (staff, volunteer, own name, none)."),
    ("camp_src", "Camp: why", ""),
    ("badge", "Camp badge", "2–3 capital letters. Blank for Rogues."),
    ("power", "Power", "1–10. Jokers 1–5."), ("power_src", "Power: why", ""),
    ("tag1", "Tag 1", ""), ("tag2", "Tag 2", "Optional. One tag is fine."), ("tags_src", "Tags: why", ""),
    ("scope", "Scope", "Self / Aura / blank."),
    ("timing", "Timing", "This round / If this wins / If this loses / blank = always on."),
    ("ability", "Ability", "Max 135 characters. Plain words."), ("ability_src", "Ability: why", ""),
    ("flavor", "Flavor text", "One short italic line."), ("flavor_src", "Flavor: why", ""),
    ("rarity", "Rarity", "Common ● / Uncommon ▲ / Rare ★"),
    ("element", "Element", "Final deck pass (ethos §10)."), ("rank", "Rank", "0 for Jokers, 1–10, or K/Q/Kn/P."),
    ("ability_value", "Ability value (est.)", "Average power the ability adds in a typical round. Used by the balance test."),
    ("balance_notes", "Balance notes", "Why power/ability were tuned."),
    # --- Art ---
    ("art_brief", "Art brief", "Scene for the portrait: who, doing what, where."), ("art_src", "Art: why", ""),
    ("art_status", "Art status", "none → prompt → generating → inbox → chosen"),
    ("art_focus", "Art crop", "Which part of the art to keep, e.g. 50% 22% (left/top)."),
    ("mj_prompt", "Midjourney prompt", "Written by the scripts. Edit the Art brief instead."),
    ("art_file_id", "Art file (auto)", "Drive file ID of the chosen art. Set by ingest-art."),
    # --- Pipeline (written by scripts) ---
    ("ai_notes", "AI notes (auto)", "Why `generate` drafted what it did."),
    ("checks", "Checks (auto)", "Ethos check results from the last run."),
    ("rules_hash", "Card hash (auto)", "Fingerprint of everything printed on the card."),
    ("rendered_hash", "Rendered hash (auto)", "Card hash at last render. Differs → needs re-rendering."),
    ("print_file_id", "Print file (auto)", "Drive file ID of the print PNG (with bleed)."),
    ("display_file_id", "Display file (auto)", "Drive file ID of the display PNG (trimmed, rounded)."),
]
GENERATED_FIELDS = ["class", "camp", "badge", "power", "tag1", "tag2", "scope", "timing",
                    "ability", "flavor", "rarity", "ability_value", "art_brief"]
# Which "why" column governs each generated field.
SRC_OF = {"class": "class_src", "camp": "camp_src", "badge": "camp_src", "power": "power_src",
          "tag1": "tags_src", "tag2": "tags_src", "scope": "ability_src", "timing": "ability_src",
          "ability": "ability_src", "flavor": "flavor_src", "art_brief": "art_src",
          # No "why" of their own: filled only while blank (ability_value also follows the ability).
          "ability_value": None, "rarity": None}
CARD_FIELDS = [k for k, _, _ in CARD_COLUMNS]
CARD_HEADER = {k: h for k, h, _ in CARD_COLUMNS}
SRC_FIELDS = [k for k in CARD_FIELDS if k.endswith("_src")]

# Dropdown lists: (list header on the Lists tab, values) and which card columns use them.
LISTS = {
    "Status": STATUSES, "Class": CLASSES, "Tag": [""] + TAGS, "Why": SOURCES, "Scope": SCOPES,
    "Timing": TIMINGS, "Rarity": RARITIES, "Element": ELEMENTS, "Art status": ART_STATUSES,
    "Yes/no": ["", "yes", "no"], "Applies to": ["All cards", "Camp", "Class", "Tag", "Card ID"],
}
DROPDOWNS = {
    "status": "Status", "class_requested": "Class", "class": "Class", "tag1": "Tag", "tag2": "Tag",
    "scope": "Scope", "timing": "Timing", "rarity": "Rarity", "element": "Element",
    "art_status": "Art status", "locked": "Yes/no", **{k: "Why" for k in SRC_FIELDS},
}

# Guidelines tab: rules for generation that apply to many cards at once.
GUIDELINE_COLUMNS = [("applies_to", "Applies to"), ("which", "Which (camp / class / tag / card ID)"),
                     ("guideline", "Guideline"), ("active", "Active")]
GUIDELINE_HEADER = dict(GUIDELINE_COLUMNS)
EXAMPLE_GUIDELINES = [
    ["All cards", "", "Follow ability-ethos: plus before minus, one ability, max 135 characters, multiplayer-safe wording.", "yes"],
    ["Camp", "The Fire Circle", "Example: make [Fire] themes prevalent. Abilities reward having other [Fire] cards around.", "no"],
    ["Class", "Joker", "Example: keep Joker power 1-5 with one clear condition for a big bonus.", "no"],
]

# People tab: contact details and reference photo. Scripts only ever read the photo (with consent).
PEOPLE_COLUMNS = [
    ("card_id", "Card ID"), ("full_name", "Full name"), ("email", "Email"), ("phone", "Phone"),
    ("photo_file_id", "Photo file ID"), ("photo_consent", "OK to use photo for AI art? (yes/no)"),
    ("form_timestamp", "Signed up"), ("notes", "Notes"),
]
PEOPLE_HEADER = dict(PEOPLE_COLUMNS)

# Settings tab rows: (key, label shown in the sheet, default, note)
SETTINGS = [
    ("set_code", "Set code", "PC1", "Prefix for card IDs."),
    ("event_line", "Event line", "unSCruz 2027 · Luminous Mycelium", "Printed bottom right of every card."),
    ("art_style", "Art style", "bold inked comic illustration, flat cel shading, thick clean linework, "
     "warm festival-night lighting, string lights, teal bioluminescent mushrooms growing along the bottom edge",
     "Added to every art prompt so the set looks consistent."),
    ("mj_params", "Midjourney parameters", "--ar 13:8 --v 7 --style raw", "Art window is 714×440 ≈ 13:8."),
    ("mj_sref", "Midjourney style reference", "", "Optional --sref URL or code."),
    ("drive_root_id", "Folder: PlayaCourt", "", "Filled in once; don't edit."),
    ("drive_photos_id", "Folder: Reference Photos", "", ""),
    ("drive_inbox_id", "Folder: Art Inbox", "", ""),
    ("drive_final_id", "Folder: Chosen Art", "", ""),
    ("drive_renders_id", "Folder: Finished Cards", "", ""),
    ("drive_print_id", "Folder: Print", "", ""),
    ("drive_display_id", "Folder: Display", "", ""),
    ("bleed_in", "Print bleed (inches)", "0.125", "Extra art/colour past the cut line on each side. 0.125 is standard."),
    ("gen_model", "Rules model", "claude-opus-5-5", "Claude model used by `generate`."),
    ("mj_queue_doc_id", "Doc: Midjourney queue", "", "Created by `prompts`."),
]
SETTINGS_DEFAULTS = {k: d for k, _, d, _ in SETTINGS}
SETTINGS_LABEL = {k: l for k, l, _, _ in SETTINGS}

# Fields allowed in anything derived for the public site.
PUBLIC_FIELDS = ["card_id", "name", "class", "camp", "badge", "power", "tag1", "tag2", "scope",
                 "timing", "ability", "flavor", "rarity", "element", "rank"]
