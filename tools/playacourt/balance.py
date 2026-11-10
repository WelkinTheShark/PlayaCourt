"""`pc.py balance`: quick Monte Carlo balance test.

Plays thousands of standard matches (best of 5, 6-card hands, cards played in random order)
with each card's strength = power + "Ability value (est.)". The class ring decides first,
then strength. This ignores the exact wording of abilities, so treat it as a smoke test:
it finds cards and classes that are clearly too strong or too weak, fast.

What-if overrides change values for this run only, e.g. --set PC1-005.power=6
"""
import random
from collections import defaultdict

from . import rules


def strength(c):
    try:
        v = float(c.get("ability_value") or 0)
    except ValueError:
        v = 0.0
    return int(c["power"]) + v


def round_winner(a, b):
    if rules.BEATS.get(a["class"]) == b["class"]:
        return 0
    if rules.BEATS.get(b["class"]) == a["class"]:
        return 1
    sa, sb = strength(a), strength(b)
    return 0 if sa > sb else 1 if sb > sa else None


def simulate(cards, matches=20000, rounds=5, hand=6, seed=1):
    rng = random.Random(seed)
    played, won = defaultdict(int), defaultdict(int)
    hand = min(hand, len(cards))
    rounds = min(rounds, hand)
    for _ in range(matches):
        hands = [rng.sample(cards, hand), rng.sample(cards, hand)]
        for h in hands:
            rng.shuffle(h)
        for r in range(rounds):
            a, b = hands[0][r], hands[1][r]
            w = round_winner(a, b)
            for c in (a, b):
                played[c["card_id"]] += 1
            if w is not None:
                won[(a, b)[w]["card_id"]] += 1
    return played, won


def report(cards, played, won, low=0.42, high=0.58):
    by_id = {c["card_id"]: c for c in cards}
    rows = sorted(((won[i] / played[i], i) for i in played if played[i]), reverse=True)
    lines = [f"{'card':9} {'name':18} {'class':7} {'str':>5} {'win%':>6}"]
    for rate, i in rows:
        c = by_id[i]
        flag = "  ← strong" if rate > high else "  ← weak" if rate < low else ""
        lines.append(f"{i:9} {c.get('name', '')[:18]:18} {c['class']:7} {strength(c):5.1f} {rate * 100:5.1f}%{flag}")
    cls_p, cls_w = defaultdict(int), defaultdict(int)
    for i in played:
        cls_p[by_id[i]["class"]] += played[i]
        cls_w[by_id[i]["class"]] += won[i]
    lines.append("")
    lines.append("By class: " + ", ".join(f"{k} {cls_w[k] / cls_p[k] * 100:.0f}%" for k in sorted(cls_p)))
    lines.append("(Ties count as not won, so 45–50% is roughly even.)")
    return "\n".join(lines)


def apply_overrides(cards, sets):
    by_id = {c["card_id"].upper(): c for c in cards}
    for s in sets or []:
        target, _, value = s.partition("=")
        cid, _, field = target.partition(".")
        if cid.upper() not in by_id or not field:
            raise SystemExit(f"bad --set '{s}': use CARD-ID.field=value, e.g. PC1-005.power=6")
        by_id[cid.upper()][field] = value
