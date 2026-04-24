# Design

This project remains harness-first:

- fixed inputs
- deterministic checks first
- persisted artifacts per run
- explicit uncertainty instead of fake confidence

## Product Expression

The harness-first core should still present itself like a product when it reaches humans.

That means the HTML report and demo surfaces should optimize for review decisions, not raw detector exhaust. A good report should answer, in order:

1. What is the confidence posture of this patch?
2. What needs human attention before trust?
3. Which detectors produced evidence, gaps, or risk?
4. Where is the full artifact trail if I need to audit details?

## Report Information Architecture

The current HTML report should preserve this structure:

1. Executive summary
2. Triage queue
3. Detector coverage
4. Full evidence lists
5. Optional review narrative

The page should feel like an inspection product, but it must stay lightweight:

- no heavy front-end dependencies
- static artifact output
- readable on desktop and mobile
- safe to archive with run artifacts

## README And Demo Posture

README and demo-facing docs should present `trust me` as a decision tool for AI-generated patches.

They should highlight:

- the generated artifact set
- the reviewer workflow
- the HTML report as the primary human-facing deliverable

They should avoid over-claiming detector certainty, because detector coverage will continue to evolve.
