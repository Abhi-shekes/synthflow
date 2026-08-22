"""Measure how re-identifiable a set of generated rows is.

k-anonymity and l-diversity, computed over *quasi-identifiers*: the columns
that are individually harmless but jointly identifying. Nobody is
identified by living in Pune; a 1983-born enterprise-plan customer in Pune
may well be the only one.

Why measure this on synthetic data at all — the rows are fabricated, so
there is no real person in them to re-identify. Two reasons it still
matters:

1. Phase 9 learns distributions, weights and correlations from real data.
   A generated row is not a copy of a real one, but a rare combination in
   the source (the only enterprise customer in a small city) stays rare in
   the output, and its rarity is exactly what makes a real individual
   findable. A synthetic dataset that reproduces a one-in-4000 combination
   has carried across the fact that such a person exists.
2. "It's synthetic, therefore it's safe" is the assumption this module
   exists to let people check rather than assume. A compliance reviewer
   needs a number, not a reassurance.

Deliberately measurement only. Nothing here suppresses, generalises or
alters a single row — the caller decides what to do about a k of 1. An
automatic fix would silently change the data's distribution, which is the
one property the user came here for.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Below this, a group is small enough that a member of it is realistically
# findable. 5 is the common regulatory floor; it is a default, not a law,
# which is why the threshold is a parameter everywhere.
DEFAULT_K = 5
DEFAULT_L = 2

# Groups listed individually in the report. A report naming 4,000 unique
# combinations is not a report anyone reads.
MAX_REPORTED_GROUPS = 10


@dataclass
class AnonymityReport:
    quasi_identifiers: list[str]
    sensitive_field: str | None
    total_rows: int
    # The size of the smallest quasi-identifier group. k=1 means at least
    # one row is unique on those columns.
    k: int
    k_threshold: int
    # Distinct sensitive values in the *least* diverse group. None when no
    # sensitive field was named. Named in full because a bare `l` is an
    # ambiguous identifier; the API still exposes it as "l", which is what
    # the literature and any compliance reviewer will call it.
    l_diversity: int | None
    l_threshold: int
    groups: int
    rows_below_k: int
    smallest_groups: list[dict[str, Any]] = field(default_factory=list)

    @property
    def k_passes(self) -> bool:
        return self.k >= self.k_threshold

    @property
    def l_passes(self) -> bool:
        return self.l_diversity is None or self.l_diversity >= self.l_threshold

    @property
    def passes(self) -> bool:
        return self.k_passes and self.l_passes

    @property
    def unique_row_share(self) -> float:
        """Share of rows sitting in a group smaller than k. The single most
        useful number in the report: "3% of rows are effectively unique on
        these columns"."""
        return self.rows_below_k / self.total_rows if self.total_rows else 0.0

    def summary(self) -> str:
        """One line for a human, phrased so it cannot be mistaken for a
        guarantee when it passes."""
        if self.total_rows == 0:
            return "No rows to measure."
        parts = [
            f"k={self.k} across {self.groups} combinations of {', '.join(self.quasi_identifiers)}"
        ]
        if self.l_diversity is not None:
            parts.append(f"l={self.l_diversity} for '{self.sensitive_field}'")
        if self.passes:
            parts.append(
                f"meets the k>={self.k_threshold} threshold — no row is "
                f"distinguishable by fewer than {self.k} others"
            )
        else:
            parts.append(
                f"below the k>={self.k_threshold} threshold: "
                f"{self.rows_below_k} of {self.total_rows} rows "
                f"({self.unique_row_share:.1%}) sit in a group that small"
            )
        return "; ".join(parts)


def _key(row: dict[str, Any], columns: list[str]) -> tuple:
    # str() so that 1 and "1" group together — a CSV round-trip changes one
    # into the other, and they identify the same person either way.
    return tuple(str(row.get(column)) for column in columns)


def measure(
    rows: list[dict[str, Any]],
    quasi_identifiers: list[str],
    *,
    sensitive_field: str | None = None,
    k_threshold: int = DEFAULT_K,
    l_threshold: int = DEFAULT_L,
) -> AnonymityReport:
    """Compute k-anonymity, and l-diversity when a sensitive field is named.

    `quasi_identifiers` are the columns an attacker is assumed to already
    know — age, city, plan, join date. Choosing them is a judgement call
    about the attacker, not something that can be derived from the data,
    which is why this takes them rather than guessing.
    """
    if not quasi_identifiers:
        raise ValueError("At least one quasi-identifier column is required.")

    if not rows:
        return AnonymityReport(
            quasi_identifiers=list(quasi_identifiers),
            sensitive_field=sensitive_field,
            total_rows=0,
            k=0,
            k_threshold=k_threshold,
            l_diversity=None,
            l_threshold=l_threshold,
            groups=0,
            rows_below_k=0,
        )

    counts: Counter[tuple] = Counter()
    sensitive: dict[tuple, set[str]] = {}
    for row in rows:
        key = _key(row, quasi_identifiers)
        counts[key] += 1
        if sensitive_field is not None:
            sensitive.setdefault(key, set()).add(str(row.get(sensitive_field)))

    k = min(counts.values())
    rows_below_k = sum(count for count in counts.values() if count < k_threshold)
    diversity = min((len(v) for v in sensitive.values()), default=None) if sensitive else None

    smallest = sorted(counts.items(), key=lambda kv: kv[1])[:MAX_REPORTED_GROUPS]
    smallest_groups = [
        {
            "values": dict(zip(quasi_identifiers, key, strict=True)),
            "rows": count,
            **(
                {"distinct_sensitive_values": len(sensitive[key])}
                if sensitive_field is not None
                else {}
            ),
        }
        for key, count in smallest
    ]

    return AnonymityReport(
        quasi_identifiers=list(quasi_identifiers),
        sensitive_field=sensitive_field,
        total_rows=len(rows),
        k=k,
        k_threshold=k_threshold,
        l_diversity=diversity,
        l_threshold=l_threshold,
        groups=len(counts),
        rows_below_k=rows_below_k,
        smallest_groups=smallest_groups,
    )
