"""Test package bootstrap.

The keyword expander caches per-word results under the user's data folder. A
test run must never read or write that cache: it would make results depend on
what a previous run happened to expand, and it would pollute the real app.
"""

try:
    import keyword_expander

    keyword_expander.PERSIST_EXPANSIONS = False
except Exception:  # optional dependency chain missing - nothing to disable
    pass
