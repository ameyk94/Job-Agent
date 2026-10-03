# ADR-001: Fresh repo, upstream imported once

Status: accepted, 2026-10-03

## Context
The project builds on MIT-licensed `jamwithai/observable-job-agent`. A fork would carry upstream
history and invite confusion about which commits are ours.

## Decision
New repo. The first commit imports the `part1.0` tree verbatim: "Import observable-job-agent part1.0 (MIT)".
All later work is ours. The README credits the original.

## Consequences
- History cleanly separates upstream code from our changes (`git diff e7e81ce..HEAD`).
- We do not track upstream changes. Any later upstream fix is ported by hand.
