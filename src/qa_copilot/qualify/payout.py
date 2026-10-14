"""Extract a USD payout hint from a listing.

Triage needs to rank by expected value, not just by "is this QA-shaped". A
bounty that pays $800 and a bounty that pays $0 are both "QA-shaped"; only one
of them is worth the afternoon.

We deliberately only match numbers that sit next to an explicit currency marker
(``$``, ``USD``, ``US$``). "40 tests to write" is not a payout, and the naive
``\\d+`` match would treat it as one.
"""

from __future__ import annotations

import re

# "$1,200" / "$300k" / "USD 250" / "1,500 USD" / "US$ 80" / "$11M"
_AMOUNT = r"\d[\d,]*(?:\.\d+)?\s*[kKmM]?"
_MONEY_RE = re.compile(
    r"(?:\$\s*(?P<a>" + _AMOUNT + r"))"
    r"|(?:(?P<b>" + _AMOUNT + r")\s*(?:usd|us\$))"
    r"|(?:(?:usd|us\$)\s*(?P<c>" + _AMOUNT + r"))",
    re.I,
)

# A number only counts as a bounty if bounty-ish language is near it. Wages and
# salaries ("$140K–$160K + equity", "$30/hr") are deliberately excluded: a yearly
# salary would otherwise swamp triage and rank a random full-time role above a
# real $500 bounty. Japanese terms skip \b because \b treats CJK as word chars.
_BOUNTY_CONTEXT = re.compile(
    r"(?i)\b(bounty|reward|prize|stipend|paid|pay|payout|grant|compensation for|"
    r"per bug|per issue)\b"
    r"|(報酬|謝礼|賞金|報奨|懸賞)"
)

# "Donate $10-$100", "sponsor us on Patreon" are money but not a payout to you.
_NOT_PAYOUT = re.compile(r"(?i)\b(donat(?:e|ion)|sponsor|patreon|tip jar|ko-?fi|fundrais)\b")

# Strong bounty words. These beat an hourly rate, so "$50/hr bounty" is kept.
_STRONG_BOUNTY = re.compile(r"(?i)\b(bounty|reward|prize|stipend)\b|(報酬|謝礼|賞金|報奨|懸賞)")

# Wage signals. "We pay $14/hr" uses a bounty-ish word ("pay") but is a wage, so
# it must not rank like a one-off bounty. "$14/hr" is not what triage is for.
_WAGE = re.compile(
    r"(?i)(/\s*hr\b|/\s*hour\b|per\s+hour|hourly|/\s*mo\b|per\s+month|monthly|"
    r"/\s*yr\b|/\s*year\b|per\s+year|per\s+annum|annual|時給|日給|月給|年収|月収|単価)"
)


def _to_float(token: str) -> float:
    cleaned = token.strip().replace(",", "").replace(" ", "")
    multiplier = 1.0
    if cleaned[-1:] in {"k", "K"}:
        multiplier = 1_000.0
        cleaned = cleaned[:-1]
    elif cleaned[-1:] in {"m", "M"}:
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return 0.0


def extract_payout(*texts: str, bounty_context: bool = False) -> tuple[float | None, str]:
    """Return the largest USD amount hinted at, plus a short human note.

    ``bounty_context=True`` means the listing is already labelled as a bounty
    (e.g. a GitHub issue with a ``bounty`` label), so a bare ``$500`` anywhere in
    the text counts. Without it, a bounty-ish word must sit on the same line, to
    keep salaries out.

    Returns ``(None, "")`` when there is no credible money signal.
    """
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return None, ""
    # A post that asks for donations is not paying you. Whole-text check: a bare
    # "$100" on its own line inside a donation post must not read as a bounty.
    if _NOT_PAYOUT.search(blob):
        return None, ""

    amounts: list[float] = []
    for match in _MONEY_RE.finditer(blob):
        token = match.group("a") or match.group("b") or match.group("c")
        if not token:
            continue
        line_start = blob.rfind("\n", 0, match.start()) + 1
        line_end = blob.find("\n", match.end())
        line = blob[line_start : line_end if line_end != -1 else len(blob)]
        # A wage is not a bounty, even when the sentence uses "pay". This is what
        # keeps a $14/hr content-review gig out of the top of triage.
        if _WAGE.search(line) and not _STRONG_BOUNTY.search(line):
            continue
        if not bounty_context and not _BOUNTY_CONTEXT.search(line):
            # Without a bounty label, a bounty-ish word must be on the same line.
            # "compensation" there means a salary band, not a one-off bounty.
            continue
        value = _to_float(token)
        # Ignore implausible dust and absurd "payouts" from concatenated numbers.
        if 5.0 <= value <= 500_000.0:
            amounts.append(value)

    if not amounts:
        return None, ""

    best = max(amounts)
    if len(amounts) > 1:
        return best, f"up to ${best:,.0f} (saw {len(amounts)} amounts)"
    return best, f"${best:,.0f}"
