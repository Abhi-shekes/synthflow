"""What generation already knew and used to discard.

The engine makes decisions on every row that nobody ever sees: it throws
away candidate rows that fail a rule and silently retries, it retries a
unique field until it finds an unused value, and it corrupts values for
error injection that a rule may then reject. All of that was computed and
dropped on the floor.

Three of these are worth surfacing because each is a *silent* failure — the
run succeeds and the data looks fine:

* **Rule discard rate.** A rule that rejects 95% of candidates still
  produces the requested rows, just slowly and from a badly skewed slice of
  the distribution. The output is not what the field config describes any
  more, and nothing says so.
* **Unique retries.** Retrying a unique field 60 times out of a possible
  100 means the pool is nearly exhausted; one more row, or a slightly
  different seed, turns that into a hard failure. Today the first sign is
  the exception.
* **Error-injection survival.** This is the interaction the generator
  docstring has documented since it was written: corruption is applied
  *before* rule checking, so a rule constraining the same field discards
  the corrupted rows. You ask for 10% bad emails, the rule says emails must
  contain "@", and you get 0% — with no error and no warning.

Collection is opt-in (`iter_rows(..., diagnostics=...)`) and costs a few
counter increments, so the streaming path stays exactly as cheap when no
one is looking. The collector is mutated during iteration and read after,
which suits a generator: Phase 8 streams rows without ever holding them
all, and this holds counters rather than rows for the same reason.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# A rule discarding more than this share of candidates has stopped being a
# constraint and started being a filter that reshapes the distribution.
HIGH_DISCARD_SHARE = 0.5

# Unique retries this close to the cap mean the next run may simply fail.
NEAR_EXHAUSTION_SHARE = 0.5

# Below this share surviving, error injection is being cancelled out by a
# rule rather than doing anything.
LOW_SURVIVAL_SHARE = 0.5


@dataclass
class GenerationDiagnostics:
    """Counters gathered while generating. Cheap, and read after the fact."""

    rows_requested: int = 0
    rows_yielded: int = 0
    # Every candidate built, including the ones rules threw away.
    candidates_generated: int = 0
    # Rule name -> candidates it rejected. Attributed to the *first* rule
    # that failed, which is what the engine itself checks, so the numbers
    # add up to `candidates_discarded` rather than double-counting a
    # candidate that would have failed several rules.
    discards_by_rule: Counter = field(default_factory=Counter)
    # Field name -> extra attempts spent finding an unused value.
    unique_retries: Counter = field(default_factory=Counter)
    # Field name -> how often corruption fired, on any candidate.
    injections_applied: Counter = field(default_factory=Counter)
    # ...and on candidates that survived to be yielded.
    injections_surviving: Counter = field(default_factory=Counter)

    @property
    def candidates_discarded(self) -> int:
        return max(0, self.candidates_generated - self.rows_yielded)

    @property
    def discard_share(self) -> float:
        if not self.candidates_generated:
            return 0.0
        return self.candidates_discarded / self.candidates_generated

    def survival_share(self, field_name: str) -> float:
        applied = self.injections_applied.get(field_name, 0)
        if not applied:
            return 0.0
        return self.injections_surviving.get(field_name, 0) / applied

    # -- recording -------------------------------------------------------

    def candidate(self, injected: set[str]) -> None:
        self.candidates_generated += 1
        for name in injected:
            self.injections_applied[name] += 1

    def accepted(self, injected: set[str]) -> None:
        self.rows_yielded += 1
        for name in injected:
            self.injections_surviving[name] += 1

    def rule_rejected(self, rule_name: str) -> None:
        self.discards_by_rule[rule_name] += 1

    def unique_retry(self, field_name: str, attempts: int) -> None:
        if attempts > 0:
            self.unique_retries[field_name] += attempts

    # -- reporting -------------------------------------------------------

    def findings(self, max_unique_attempts: int) -> list[str]:
        """Human-readable observations, phrased as what happened rather than
        as a verdict. Empty when there is nothing to say — a report that
        always has content trains people to ignore it."""
        out: list[str] = []

        if self.discard_share >= HIGH_DISCARD_SHARE:
            out.append(
                f"{self.discard_share:.0%} of generated candidates were discarded by rules "
                f"({self.candidates_discarded} of {self.candidates_generated}). The rows you "
                f"got are the ones that happened to pass, so the output no longer matches "
                f"what the field configuration describes."
            )

        for rule_name, count in self.discards_by_rule.most_common():
            share = count / self.candidates_generated if self.candidates_generated else 0
            if share >= HIGH_DISCARD_SHARE:
                out.append(
                    f"rule '{rule_name}' rejected {count} candidates ({share:.0%} of all "
                    f"attempts) — it is doing more filtering than constraining"
                )

        for field_name, retries in self.unique_retries.most_common():
            average = retries / self.rows_yielded if self.rows_yielded else 0
            if average >= max_unique_attempts * NEAR_EXHAUSTION_SHARE:
                out.append(
                    f"unique field '{field_name}' averaged {average:.0f} retries per row "
                    f"against a cap of {max_unique_attempts} — the pool of possible values "
                    f"is nearly exhausted and a larger run is likely to fail outright"
                )

        for field_name, applied in self.injections_applied.most_common():
            survival = self.survival_share(field_name)
            if survival < LOW_SURVIVAL_SHARE:
                surviving = self.injections_surviving.get(field_name, 0)
                out.append(
                    f"error injection on '{field_name}' fired {applied} times but only "
                    f"{surviving} survived ({survival:.0%}) — corruption is applied before "
                    f"rules are checked, so a rule constraining this field is discarding "
                    f"the corrupted rows"
                )

        return out

    def as_dict(self, max_unique_attempts: int) -> dict:
        return {
            "rows_requested": self.rows_requested,
            "rows_yielded": self.rows_yielded,
            "candidates_generated": self.candidates_generated,
            "candidates_discarded": self.candidates_discarded,
            "discard_share": round(self.discard_share, 4),
            "discards_by_rule": dict(self.discards_by_rule),
            "unique_retries": dict(self.unique_retries),
            "injections_applied": dict(self.injections_applied),
            "injections_surviving": dict(self.injections_surviving),
            "injection_survival_share": {
                name: round(self.survival_share(name), 4) for name in self.injections_applied
            },
            "findings": self.findings(max_unique_attempts),
        }
