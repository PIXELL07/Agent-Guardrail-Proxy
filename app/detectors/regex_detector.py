"""
Tier 1: regex/heuristic detection.

This is the cheapest, fastest tier -- pure string matching, no model calls.
It exists to catch the "low effort" injection attempts that show up
constantly in the wild: text embedded in a scraped webpage or document
telling the agent to ignore its instructions, exfiltrate data, or call a
different tool than intended.

It will never catch a well-paraphrased attack -- that's what tiers 2 and 3
are for. Its job is to filter out the easy 60-70% of cases so the more
expensive tiers only see the harder ones.
"""

from __future__ import annotations

import re

from app.schemas import TierResult

# Each pattern targets a *category* of injection behavior, not an exact
# phrase, so minor rewording of the same idea still gets caught.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|all)\b.{0,30}\b(instructions?|prompts?|rules?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_reassignment",
        re.compile(
            r"\byou are now\b|\bnew (system )?instructions?\b|\bact as\b.{0,20}\binstead\b",
            re.IGNORECASE,
        ),
    ),
    (
        "data_exfiltration",
        re.compile(
            r"\bsend\b.{0,30}\b(api key|password|secret|credentials|token)\b.{0,40}\bto\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hidden_directive_marker",
        re.compile(
            r"\[system\]|\[/?INST\]|<\|.*?\|>|###\s*(system|admin|override)",
            re.IGNORECASE,
        ),
    ),
    (
        "tool_redirect",
        re.compile(
            r"\binstead of\b.{0,30}\bcall\b|\buse the\b.{0,20}\btool\b.{0,20}\binstead\b",
            re.IGNORECASE,
        ),
    ),
]


def check_regex(text: str) -> TierResult:
    """Run all known injection patterns against a text blob."""
    for label, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            return TierResult(
                tier="regex",
                triggered=True,
                confidence=0.9,
                reason=f"Matched known pattern category '{label}': {match.group(0)!r}",
            )
    return TierResult(
        tier="regex",
        triggered=False,
        confidence=0.0,
        reason="No known injection patterns matched",
    )
