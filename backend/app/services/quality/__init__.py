"""Data quality and validation: what the engine observed while generating,
what the generated rows actually look like, and whether they satisfy the
user's own assertions.

Entry points are
`app.services.quality.diagnostics.GenerationDiagnostics` (collected during
generation), `app.services.quality.observe.observe_rows` (what came out),
and `app.services.quality.assertions.check` (did it meet the bar).
"""
