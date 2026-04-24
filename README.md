# trust me

Not another AI code reviewer.

`trust me` is a patch-confidence harness. It does not try to prove AI-written code is correct. It shows what was actually verified, what remains unverified, what looks risky, and what a human should inspect before trusting the patch.

## Product Snapshot

`trust me` is built for the uncomfortable moment after an AI tool hands you a patch and says it is done.

Instead of another "LGTM-style" summary, you get a decision surface:

- what passed
- what is still missing evidence
- what looks suspicious
- what a human reviewer should do next

The generated HTML report is meant to feel like a product artifact, not a debug dump. It leads with confidence posture, review queue, detector coverage, and the exact follow-up items a reviewer should triage.

## Demo Flow

Run against the current working tree:

```bash
python3 -m trust_me.cli run --root .
```

Run against a patch and ask Claude for a tester-style review summary:

```bash
python3 -m trust_me.cli run --root . --patch examples/verification.patch --with-review
```

Each run is persisted under `runs/run_YYYY_MM_DD_HHMMSS/`.

Open `report.html` in that run directory to see the product-style inspection page. The page now emphasizes:

- confidence posture and merge caution level
- a prioritized review queue for suspicious and unresolved items
- detector-by-detector coverage cards
- a narrative summary when `--with-review` is enabled

## What You Get

For a working tree, diff, or patch file, `trust me` produces four top-level buckets:

- `verified`
- `unverified`
- `suspicious`
- `action_items`

Artifacts saved per run:

| File | Purpose |
| --- | --- |
| `summary.json` | small run metadata and counts |
| `report.json` | full normalized report payload |
| `findings.jsonl` | detector outputs as line-delimited records |
| `report.html` | product-style inspection report for humans |
| `commands.json` | invocation context |
| `raw_diff.patch` | captured diff or patch text |

## Report Anatomy

The HTML report is designed to answer three product questions quickly:

1. Should I trust this patch enough to move forward?
2. What exactly still needs human attention?
3. Which detectors produced evidence versus uncertainty?

That is why the page is organized around:

- an executive confidence summary
- a reviewer triage queue
- detector coverage cards
- full verified, unverified, suspicious, and action-item lists

## Why This Exists

AI coding tools make it cheap to generate patches.
The harder problem is knowing when the patch is still not trustworthy.

This repo is a harness for that gap.

## Current Signals

Implemented today:

- lint status
- type-check status
- build smoke check
- test status
- import check
- diff scope check
- core-file risk check
- optional Claude review summary

## Position

`trust me` does not say "looks good".
It shows the evidence, the missing evidence, and the remaining blast radius.
