# AI-USAGE.md — LPDG Innovation Hub Selection Challenge 2026

## What I used AI tools for

- **Code structure and architecture:** Used AI to help design the multi-signal scoring approach, including which telemetry metrics to combine, how to weight them, and how to structure the modular scoring pipeline.
- **Data exploration:** Used AI to generate exploration scripts that identified the engineer review labels as a key signal, found the meter read rate correlation with bad gateways, and characterised the field visit patterns.
- **Reason generation:** Used AI to write the reason-generation logic that produces human-readable explanations for each ranked gateway selection.
- **Documentation:** Used AI to draft DECISIONS.md and this file based on the choices made during development.

## One thing AI got wrong that I spotted

AI initially suggested using the engineer review labels for all weeks, including those before 15 Feb 2026 (the review date). This would have been data leakage — using information from the future to make predictions about the past. I corrected this by only incorporating the labels for weeks starting on or after 15 Feb 2026, and excluding them entirely for earlier weeks. The validation confirmed the predictions remain correct regardless of when labels are available.
