"""The card workbook's shape: tabs, columns and allowed values.

All card data lives in Google Drive (PlayaCourt/Playa Court Cards). Column headers in the sheet
are plain English; the scripts map them to the short keys used in code via the tables below.
`pc.py upgrade-sheet` adds any tab or column defined here that the sheet is missing.
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
    "AI draft",     # drafted by Claude Code (`apply`); redrafted freely until you change the why
    "Placeholder",  # stand-in; must be replaced before the card is approved
]

STATUSES = ["submitted", "drafting", "review", "approved", "printed", "withdrawn", "example"]
PUBLISHED_STATUSES = {"approved", "printed", "example"}
ART_STATUSES = ["none", "prompt", "generating", "inbox", "chosen"]

TAB_CARDS, TAB_PEOPLE, TAB_SETTINGS, TAB_LISTS = "Cards", "People (private)", "Settings", "Lists"
TAB_GUIDELINES, TAB_CAMPS = "Guidelines", "Camps"
YES = {"yes", "y", "true", "x", "1"}

# A field counts as yours (never redrafted) when its "why" is one of these.
OWNED_SOURCES = {"Form", "Known", "Balance", "Ethos"}

# (key used in code, sheet header, note)
CARD_COLUMNS = [
    # --- Card ---
    ("card_id", "Card ID", "Set code + number, e.g. PC1-007. Never reuse an ID."),
    ("status", "Status", "submitted → drafting → review → approved → printed (or withdrawn)."),
    ("locked", "Locked", "yes = finalized. Drafting, prompts, new art and render all leave this card alone."),
    ("name", "Name", "Name or playa name as printed on the card."),
    # --- From the sign-up form ---
    ("class_requested", "Class they picked", "Class chosen on the sign-up form."),
    ("camp_raw", "Camp they wrote", "Camp exactly as written on the form."),
    ("known_for_1", "Known for 1", "From the form."),
    ("known_for_2", "Known for 2", "From the form."),
    ("known_for_3", "Known for 3", "From the form."),
    ("form_extras", "Form extras", "Other form answers, kept for context."),
    # --- Your custom info for this camper ---
    ("my_input", "What I know about them", "Your own knowledge of the person. Used for rules and art."),
    ("guidelines", "Card guidelines", "Instructions for this card's rules, e.g. 'make it a combo piece with [Fire]'."),
    ("art_notes", "Art notes", "Art direction for this person: pose, outfit, props, mood."),
    # --- Card design (each with a 'why') ---
    ("class", "Class", "The card's class."), ("class_src", "Class: why", "Form / Known / Balance / Ethos / AI draft / Placeholder"),
    ("camp", "Camp", "Printed camp. Leave blank for a Rogue (staff, volunteer, own name, none)."),
    ("camp_src", "Camp: why", ""),
    ("badge", "Camp badge", "2–3 capital letters. Blank for Rogues. Comes from the Camps tab."),
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
    ("mj_prompt", "Midjourney prompt", "Written by the scripts. Edit Art brief / Art notes / the camp instead."),
    ("art_file_id", "Art file (auto)", "Drive file ID of the chosen art. Set by ingest-art or set-art."),
    # --- Pipeline (written by scripts) ---
    ("camp_key", "Camp key (auto)", "Which Camps row this camper belongs to."),
    ("ai_notes", "AI notes (auto)", "Why the draft made the choices it did."),
    ("checks", "Checks (auto)", "Ethos check results from the last run."),
    ("rules_hash", "Card hash (auto)", "Fingerprint of everything printed on the card."),
    ("rendered_hash", "Rendered hash (auto)", "Card hash at last render. Differs → needs re-rendering."),
    ("print_file_id", "Print file (auto)", "Drive file ID of the print PNG (with bleed)."),
    ("trim_file_id", "Print (no bleed) file (auto)", "Drive file ID of the print PNG without bleed."),
    ("display_file_id", "Display file (auto)", "Drive file ID of the display PNG (trimmed, rounded)."),
]
GENERATED_FIELDS = ["class", "camp", "badge", "power", "tag1", "tag2", "scope", "timing",
                    "ability", "flavor", "rarity", "ability_value", "art_brief"]
# Which "why" column governs each drafted field.
SRC_OF = {"class": "class_src", "camp": "camp_src", "badge": "camp_src", "power": "power_src",
          "tag1": "tags_src", "tag2": "tags_src", "scope": "ability_src", "timing": "ability_src",
          "ability": "ability_src", "flavor": "flavor_src", "art_brief": "art_src",
          # No "why" of their own: filled only while blank (ability_value also follows the ability).
          "ability_value": None, "rarity": None}
CARD_FIELDS = [k for k, _, _ in CARD_COLUMNS]
CARD_HEADER = {k: h for k, h, _ in CARD_COLUMNS}
SRC_FIELDS = [k for k in CARD_FIELDS if k.endswith("_src")]

# Camps tab: one row per camp, so every member's card is coordinated.
CAMP_COLUMNS = [
    ("camp", "Camp", "Name as printed on cards."),
    ("aliases", "Aliases", "Other spellings people used on the form, comma-separated."),
    ("badge", "Badge", "2–3 capital letters shared by every member's card."),
    ("rogue", "Not a real camp? (yes = Rogue)", "yes for staff, volunteers, own names, 'none': members get no camp."),
    ("theme", "Camp theme", "What the camp is about, in a sentence."),
    ("rule_themes", "Rule themes", "Tags or mechanics members' abilities should lean on, e.g. 'reward other [Fire] cards'."),
    ("art_setting", "Art setting", "Scene used in every member's art, e.g. 'around a stone fire ring at night'."),
    ("art_motifs", "Art motifs & colours", "Recurring props, symbols and colours for the camp's art."),
    ("notes", "Notes", "Anything else to keep in mind."),
    ("status", "Status (auto)", "new = added by intake, needs a look. ok = reviewed."),
    ("locked", "Locked", "yes = drafting never changes this camp."),
]
CAMP_FIELDS = [k for k, _, _ in CAMP_COLUMNS]
CAMP_HEADER = {k: h for k, h, _ in CAMP_COLUMNS}
CAMP_DRAFT_FIELDS = ["badge", "rogue", "theme", "rule_themes", "art_setting", "art_motifs"]

# Dropdown lists: (list header on the Lists tab, values) and which columns use them.
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

# Guidelines tab: rules for drafting that apply to many cards at once.
GUIDELINE_COLUMNS = [("applies_to", "Applies to"), ("which", "Which (camp / class / tag / card ID)"),
                     ("guideline", "Guideline"), ("active", "Active")]
GUIDELINE_HEADER = dict(GUIDELINE_COLUMNS)
EXAMPLE_GUIDELINES = [
    ["All cards", "", "Follow ability-ethos: plus before minus, one ability, max 135 characters, multiplayer-safe wording.", "yes"],
    ["Camp", "The Fire Circle", "Example: make [Fire] themes prevalent. Abilities reward having other [Fire] cards around.", "no"],
    ["Class", "Joker", "Example: keep Joker power 1-5 with one clear condition for a big bonus.", "no"],
]

# People tab: contact details and reference photo. Never put into drafting packets.
PEOPLE_COLUMNS = [
    ("card_id", "Card ID"), ("full_name", "Full name"), ("email", "Email"), ("phone", "Phone"),
    ("photo_file_id", "Photo file ID"), ("photo_consent", "OK to use photo for AI art? (yes/no)"),
    ("form_timestamp", "Signed up"), ("notes", "Notes"),
]
PEOPLE_HEADER = dict(PEOPLE_COLUMNS)

# Form responses → fields. Each key matches the first response column whose header contains
# any of the phrases (case-insensitive). Unmatched columns go to Form extras.
FORM_MAP = [
    ("form_timestamp", ["timestamp"]),
    ("email", ["email"]),
    ("phone", ["phone"]),
    ("full_name", ["full name", "legal name", "real name"]),
    ("name", ["playa name", "card name", "name on", "your name", "name"]),
    ("camp_raw", ["camp"]),
    ("class_requested", ["class"]),
    ("known_for_1", ["known for 1", "first thing", "thing 1", "known for"]),
    ("known_for_2", ["known for 2", "second thing", "thing 2"]),
    ("known_for_3", ["known for 3", "third thing", "thing 3"]),
    ("photo_file_id", ["photo", "picture", "upload"]),
    ("photo_consent", ["consent", "ok to use", "permission"]),
]
PEOPLE_FORM_FIELDS = {"form_timestamp", "email", "phone", "full_name", "photo_file_id", "photo_consent"}

# Settings tab rows: (key, label shown in the sheet, default, note)
SETTINGS = [
    ("set_code", "Set code", "PC1", "Prefix for card IDs."),
    ("event_line", "Event line", "unSCruz 2027 · Luminous Mycelium", "Printed bottom right of every card."),
    ("art_style", "Art style", "bold inked comic illustration, flat cel shading, thick clean linework, "
     "warm festival-night lighting, string lights, teal bioluminescent mushrooms growing along the bottom edge",
     "Added to every art prompt so the set looks consistent."),
    ("mj_params", "Midjourney parameters", "--ar 13:8 --v 7 --style raw", "Art window is 714×440 ≈ 13:8."),
    ("mj_sref", "Midjourney style reference", "", "Optional --sref URL or code."),
    ("responses_sheet_id", "Form responses sheet", "", "ID of the linked Form responses Sheet (shared with this account)."),
    ("responses_tab", "Form responses tab", "Form Responses 1", "Tab name inside the responses Sheet."),
    ("drive_root_id", "Folder: PlayaCourt", "", "Filled in once; don't edit."),
    ("drive_photos_id", "Folder: Reference Photos", "", ""),
    ("drive_inbox_id", "Folder: Art Inbox", "", ""),
    ("drive_final_id", "Folder: Chosen Art", "", ""),
    ("drive_renders_id", "Folder: Finished Cards", "", ""),
    ("drive_print_id", "Folder: Print", "", ""),
    ("drive_trim_id", "Folder: Print (no bleed)", "", ""),
    ("drive_display_id", "Folder: Display", "", ""),
    ("bleed_in", "Print bleed (inches)", "0.125", "Extra art/colour past the cut line on each side. 0.125 is standard."),
    ("mj_queue_doc_id", "Doc: Midjourney queue", "", "Created by `prompts`."),
]
SETTINGS_DEFAULTS = {k: d for k, _, d, _ in SETTINGS}
SETTINGS_LABEL = {k: l for k, l, _, _ in SETTINGS}

# Tabs `upgrade-sheet` ensures exist, with their header rows.
TAB_HEADERS = {
    TAB_CARDS: [h for _, h, _ in CARD_COLUMNS],
    TAB_CAMPS: [h for _, h, _ in CAMP_COLUMNS],
    TAB_GUIDELINES: [h for _, h in GUIDELINE_COLUMNS],
    TAB_PEOPLE: [h for _, h in PEOPLE_COLUMNS],
    TAB_SETTINGS: ["Setting", "Value", "What it is for"],
}

# Fields allowed in anything derived for the public site.
PUBLIC_FIELDS = ["card_id", "name", "class", "camp", "badge", "power", "tag1", "tag2", "scope",
                 "timing", "ability", "flavor", "rarity", "element", "rank"]
