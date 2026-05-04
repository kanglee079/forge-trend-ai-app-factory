# Autopilot Architecture

Autopilot is the supervision layer over the existing agent pipeline.

States:

- idle
- planning
- researching
- designing
- coding
- testing
- fixing
- evaluating
- packaging
- learning
- complete
- blocked

The current implementation records Autopilot timeline events, automatically retries QA fixes through the existing repair loop, attempts bounded policy/quality fixes, and records a run evaluation into Learning Memory.

Production publishing remains blocked and human approval is required.
