---
name: recovery
description: Use as soon as a test, command or validation step fails during a TASK. Classifies the failure, enforces the retry budget, and produces the BLOCKED report.
---

# Recovery

1. Classify the failure: CODE, TEST, ENVIRONMENT, SPECIFICATION,
   ARCHITECTURE or TOOLING (table in `governance/RECOVERY.md` R1).
   - ENVIRONMENT, SPECIFICATION or ARCHITECTURE: stop now and go to
     step 6.
   - TOOLING: retry once, unchanged; if it fails again, go to step 6.
2. Check the packet's Baseline section. If this failure was already there
   before your change, it is not yours. Note it in `limitations` and
   continue.
3. Reproduce the failure with one test node:
   `uv run pytest <file>::<test> -q -x`.
4. Write one hypothesis, make the smallest change, and re-run that node.
   Record the attempt (failure_id, class, command, error_excerpt <= 20
   lines, hypothesis, change, result, next).
5. Budget: at most 2 attempts per hypothesis and 3 hypotheses. Stop
   early if two attempts in a row taught you nothing new.
6. BLOCKED: stop editing and leave the tree as it is. In the final JSON
   report, set `status: "BLOCKED"` and fill `blocker` with class,
   summary, evidence, `needed` (the smallest decision or resource that
   unblocks you) and `conflicting_ids`.

Never: delete, skip or xfail a test; loosen atol/rtol/approx; mock the
thing under test; add `noqa` or `type: ignore`; edit outside scope; claim
a check you did not run.
