"""Render finished card PNGs from card data + art, with headless Chrome (Playwright).

Two versions per card, both at 600 dpi (the 750 x 1050 layout at 2x):
- print:   the card plus bleed on every side (default 0.125 in → 1650 x 2250), square
           corners, band and background colours running past the cut line.
- display: the trimmed card (1500 x 2100) with rounded corners on transparency.
"""
import base64
import html
import mimetypes
from pathlib import Path

from . import rules

TEMPLATE = (Path(__file__).parent / "card.html").read_text(encoding="utf-8")
DARK = "#1E1A16"


def symbol_svg(kind, fill, stroke=DARK, sw=7, box="0 0 136 112"):
    """Element symbols from the card back: fire △, water ▽, air △ with bar, earth ▽ with bar, spirit ●."""
    up, down = "68,6 130,104 6,104", "6,8 130,8 68,106"
    shape = {
        "fire": f'<polygon points="{up}"/>',
        "air": f'<polygon points="{up}"/><line x1="2" y1="70" x2="134" y2="70"/>',
        "water": f'<polygon points="{down}"/>',
        "earth": f'<polygon points="{down}"/><line x1="2" y1="42" x2="134" y2="42"/>',
        "spirit": '<circle cx="68" cy="56" r="50"/>',
    }[kind]
    return (f'<svg viewBox="{box}" xmlns="http://www.w3.org/2000/svg"><g fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round">{shape}</g></svg>')


# Outlined rarity marks, as printed: Common ○, Uncommon △, Rare ☆.
_R = '<svg viewBox="0 0 24 24"><g fill="none" stroke="#F4ECDD" stroke-width="2.5" stroke-linejoin="round">{}</g></svg>'
RARITY_SVG = {
    "Common": _R.format('<circle cx="12" cy="12.5" r="8"/>'),
    "Uncommon": _R.format('<path d="M12 4L21 20H3z"/>'),
    "Rare": _R.format('<path d="M12 3.2l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6-4.5-4.2 6.1-.7z"/>'),
}

# Vertical position of the power digit inside each symbol (centroid differs).
GEM_TOP = {"fire": 26, "air": 26, "water": 2, "earth": 2, "spirit": 16}
SET_SYMBOL = ('<svg class="set" viewBox="0 0 24 24"><path d="M2.5 12.5C2.5 7 6.8 3 12 3s9.5 4 9.5 9.5z" fill="#3FD9C8" '
              'stroke="#0E3B37" stroke-width="1.2" stroke-linejoin="round"/><path d="M9.3 12.5h5.4l.8 7.2a1.6 1.6 0 0 1-1.6 '
              '1.8h-3.8a1.6 1.6 0 0 1-1.6-1.8z" fill="#D8FBF5" stroke="#0E3B37" stroke-width="1.2" stroke-linejoin="round"/></svg>')


def card_html(card, settings, art_path=None, mode="display"):
    e = lambda s: html.escape(str(s or ""))
    cls = card.get("class", "Joker")
    st = rules.CLASS_STYLE.get(cls, rules.CLASS_STYLE["Joker"])
    beats = rules.BEATS.get(cls, "")
    bst = rules.CLASS_STYLE.get(beats, st)
    power = str(card.get("power", "")).strip()
    gem_fill = f"color-mix(in srgb,{st['band']} 80%,#000)"
    sub = cls.upper() + (f" · {card['camp']}" if card.get("camp") else "")
    typeline = cls + " · " + " ".join(f"[{t}]" for t in rules.tags(card))
    lbl = rules.label(card)
    set_code, _, num = card.get("card_id", "").partition("-")
    footer = f"{set_code} · {num}" + ("" if card.get("status") in ("approved", "printed", "example") else " · draft")
    if art_path:
        raw = Path(art_path).read_bytes()
        mime = ("image/jpeg" if raw[:2] == bytes([0xFF, 0xD8]) else "image/webp" if raw[8:12] == b"WEBP"
                else mimetypes.guess_type(str(art_path))[0] or "image/png")
        data = base64.b64encode(raw).decode()
        art_html = f'<img src="data:{mime};base64,{data}" style="object-position:{e(card.get("art_focus") or "50% 30%")}">'
    else:
        art_html = '<div class="pending">ART PENDING</div>'
    gem_style = f"top:{GEM_TOP[st['symbol']]}px" + (";text-decoration:underline;text-decoration-thickness:6px;text-underline-offset:4px" if power in ("6", "9") else "")
    parts = [
        f'<div class="card" style="--band:{st["band"]};--ink:{st["ink"]};--bink:{bst["ink"]}">',
        '<div class="band"></div><div class="plate"></div>',
        f'<div class="name">{e(card.get("name"))}</div><div class="sub">{e(sub)}</div>',
        f'<div class="badge">{e(card.get("badge"))}</div>' if card.get("camp") and card.get("badge") else "",
        f'<div class="gemsym">{symbol_svg(st["symbol"], gem_fill)}</div>',
        f'<div class="gem" style="{gem_style}">{e(power)}</div>',
        f'<div class="artwin">{art_html}</div>',
        f'<div class="typebar"></div><div class="typeline">{e(typeline)}</div>{SET_SYMBOL}',
        '<div class="rules"></div>',
        f'<div class="beats"><span class="lbl">Beats</span>{symbol_svg(bst["symbol"], bst["band"], sw=9)}'
        f'<span class="cls">{e(beats)}</span></div>',
        f'<div class="label">{e(lbl)}</div>' if lbl else "",
        f'<div class="ability{"" if lbl else " up"}">{e(card.get("ability"))}</div>',
        f'<div class="flavor">{e(card.get("flavor"))}</div>',
        f'<div class="rarity">{RARITY_SVG.get(card.get("rarity", ""), "")}</div>',
        f'<div class="footer">{e(footer)}</div>',
        f'<div class="event">{e(settings.get("event_line"))}</div>',
        "</div>",
    ]
    body = "".join(parts)
    if mode == "print":
        bleed = float(settings.get("bleed_in") or 0.125) * 300  # layout is 300 px per inch
        body = (f'<div class="sheet" style="--bleed:{bleed}px;--band:{st["band"]}">'
                f'<div class="strip"></div>{body}</div>')
    return TEMPLATE.replace("{{CARD}}", body)


def render(cards, settings, out_dir, art_paths):
    """Write <out_dir>/<id>-print.png and <id>-display.png for each card.
    art_paths: {card_id: local image path or None}. Returns {card_id: (print, display)}."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome")
        page = br.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
        for c in cards:
            paths = []
            for mode, sel in (("print", ".sheet"), ("display", ".card")):
                page.set_content(card_html(c, settings, art_paths.get(c["card_id"]), mode), wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                path = out_dir / f"{c['card_id']}-{mode}.png"
                page.locator(sel).screenshot(path=str(path), omit_background=(mode == "display"))
                paths.append(path)
            out[c["card_id"]] = tuple(paths)
        br.close()
    return out
