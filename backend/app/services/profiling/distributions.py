"""Fit a continuous distribution to a column of numbers, and express the
winner as a SynthFlow formula.

No numpy or scipy. Everything needed is in `statistics`: means, standard
deviations, and — importantly — `NormalDist.inv_cdf`, which gives the
theoretical quantiles used to score candidate fits. Keeping the core
image free of a ~90 MB numerical stack matters more here than the last
few percent of fitting sophistication, and Phase 5's modular-install work
means a heavier fitter could always arrive later as an optional extra.

Candidates are scored by comparing empirical deciles against the fitted
distribution's, normalised by the sample's spread — a crude
Kolmogorov–Smirnov-ish distance. It is not a hypothesis test and doesn't
claim to be: it picks the best of a handful of shapes and reports how
well it matched, so a user can see "normal, fit 0.03" and judge it.
"""

import math
import statistics as st
from dataclasses import dataclass

from app.services.privacy.bounds import round_bounds

# Below this many usable values, fitting is guesswork — fall back to a
# plain uniform range rather than inventing a shape from six points.
MIN_SAMPLES_FOR_FIT = 30

# Deciles, avoiding the extreme tails where a single outlier dominates.
_QUANTILES = [i / 10 for i in range(1, 10)]


@dataclass
class Fit:
    """A fitted distribution and how well it matched."""

    kind: str
    # A SynthFlow expression that samples it, e.g. "gauss(41.2, 12.1)".
    expression: str
    # Lower is better; roughly "average decile error as a fraction of spread".
    distance: float
    params: dict[str, float]

    @property
    def quality(self) -> str:
        if self.distance < 0.05:
            return "close"
        if self.distance < 0.15:
            return "approximate"
        return "rough"


def _r(value: float) -> float:
    """Round for display in a formula — a fitted parameter with 15
    decimal places implies precision the sample doesn't support."""
    return round(value, 4)


def _empirical_quantiles(values: list[float]) -> list[float]:
    ordered = sorted(values)
    n = len(ordered)
    out = []
    for q in _QUANTILES:
        # Nearest-rank; fine at these sample sizes and avoids interpolation
        # subtleties that wouldn't change which distribution wins.
        index = min(n - 1, max(0, int(round(q * (n - 1)))))
        out.append(ordered[index])
    return out


def _score(values: list[float], theoretical: list[float]) -> float:
    empirical = _empirical_quantiles(values)
    spread = max(values) - min(values)
    if spread <= 0:
        return 0.0
    return sum(abs(a - b) for a, b in zip(empirical, theoretical, strict=True)) / (
        len(empirical) * spread
    )


def _try_normal(values: list[float]) -> Fit | None:
    mu, sigma = st.mean(values), st.stdev(values)
    if sigma <= 0:
        return None
    dist = st.NormalDist(mu, sigma)
    theoretical = [dist.inv_cdf(q) for q in _QUANTILES]
    return Fit(
        kind="normal",
        expression=f"gauss({_r(mu)}, {_r(sigma)})",
        distance=_score(values, theoretical),
        params={"mean": _r(mu), "stddev": _r(sigma)},
    )


def _try_lognormal(values: list[float]) -> Fit | None:
    # Only defined for strictly positive data.
    if any(v <= 0 for v in values):
        return None
    logs = [math.log(v) for v in values]
    mu, sigma = st.mean(logs), st.stdev(logs)
    if sigma <= 0:
        return None
    dist = st.NormalDist(mu, sigma)
    theoretical = [math.exp(dist.inv_cdf(q)) for q in _QUANTILES]
    return Fit(
        kind="lognormal",
        expression=f"lognormal({_r(mu)}, {_r(sigma)})",
        distance=_score(values, theoretical),
        params={"log_mean": _r(mu), "log_stddev": _r(sigma)},
    )


def _try_exponential(values: list[float]) -> Fit | None:
    if any(v < 0 for v in values):
        return None
    mean = st.mean(values)
    if mean <= 0:
        return None
    lambd = 1 / mean
    theoretical = [-math.log(1 - q) / lambd for q in _QUANTILES]
    return Fit(
        kind="exponential",
        expression=f"expo({_r(lambd)})",
        distance=_score(values, theoretical),
        params={"rate": _r(lambd)},
    )


def _try_uniform(values: list[float]) -> Fit:
    # Bounds are rounded outward before anything else uses them, so the
    # exact minimum and maximum of the sample — two real records' values —
    # never reach the expression. Scored against the rounded bounds rather
    # than the raw ones, because the rounded range is what will actually be
    # generated and the reported fit quality should describe that.
    low, high = round_bounds(min(values), max(values))
    theoretical = [low + q * (high - low) for q in _QUANTILES]
    return Fit(
        kind="uniform",
        expression=f"uniform({_r(low)}, {_r(high)})",
        distance=_score(values, theoretical),
        params={"low": _r(low), "high": _r(high)},
    )


def fit_best(values: list[float]) -> Fit | None:
    """Pick the best-matching distribution, or None if there's too little
    data to justify guessing at a shape."""
    usable = [float(v) for v in values if v is not None]
    if len(usable) < MIN_SAMPLES_FOR_FIT:
        return None
    if len(set(usable)) < 2:
        return None

    candidates = [
        fit
        for fit in (
            _try_normal(usable),
            _try_lognormal(usable),
            _try_exponential(usable),
            _try_uniform(usable),
        )
        if fit is not None
    ]
    if not candidates:
        return None

    best = min(candidates, key=lambda f: f.distance)

    # Prefer uniform when nothing fits meaningfully better: it makes no
    # claim about shape, so it's the honest default rather than a
    # confidently-wrong bell curve.
    uniform = next((c for c in candidates if c.kind == "uniform"), None)
    if uniform is not None and best.distance > uniform.distance * 0.9:
        return uniform
    return best
