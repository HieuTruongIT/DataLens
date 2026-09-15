# Contributing

Create a virtual environment and install requirements as described in README.
Run `python -m pytest -q -W error` before submitting a change.

Keep detection, scoring, transformation and serialization outside Streamlit views.
For a new detector, document its assumptions, severity, affected unit and whether
it contributes to the score. Add a small test that establishes its actual behavior.
For a cleaning action, test the output, source immutability, ordering, invalid
parameters and new missing values. Never turn a detected issue into an automatic
transformation.

Use synthetic fixtures only. Do not attach private datasets to issues or commit
uploads, virtual environments, caches, credentials or temporary exports.
Bug reports should include a minimal synthetic example, expected and actual
behavior, Python/dependency versions and the command used.

Keep changes focused. Explain what changed and how it was validated.
UI changes should be exercised in the running app; screenshots must be real.
