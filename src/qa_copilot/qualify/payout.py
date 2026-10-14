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

# "$1,200" / "$300k" / "USD 250" / "1,500 USD" / "US$ 80"
_AMOUNT = r"\d[\d,]*(?:\.\d+)?\s*[kK]?"
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


def _to_float(token: str) -> float:
    cleaned = token.strip().replace(",", "").replace(" ", "")
    multiplier = 1.0
    if cleaned[-1:] in {"k", "K"}:
        multiplier = 1000.0
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return 0.0


def extract_payout(*texts: str) -> tuple[float | None, str]:
    """Return the largest USD amount hinted at, plus a short human note.

    Returns ``(None, "")`` when there is no credible money signal.
    """
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return None, ""

    amounts: list[float] = []
    for match in _MONEY_RE.finditer(blob):
        token = match.group("a") or match.group("b") or match.group("c")
        if not token:
            continue
        # Guard: require bounty language on the same line. "compensation" here
        # means a salary band, not a one-off bounty.
        line_start = blob.rfind("\n", 0, match.start()) + 1
        line_end = blob.find("\n", match.end())
        line = blob[line_start : line_end if line_end != -1 else len(blob)]
        if not _BOUNTY_CONTEXT.search(line):
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
