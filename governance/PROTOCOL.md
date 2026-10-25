# Context-efficient execution protocol

How a task travels from spec to merged code. The ARCHITECT and the tools
follow this; the WORKER only sees its result (a packet).

## 1. Context loading (for the worker)

| Layer | Source | Loaded | Budget |
| --- | --- | --- | --- |
| Always-on rules | root + package `AGENTS.md` (Codex auto-load) | Every task | <= 1,000 tok |
| Core principles | `CONSTITUTION.md` CORE block, verbatim | Every packet | <= 800 |
| Task contract | `tasks/TASK-*.toml` rendered | This task | <= 1,500 |
| Requirements | cited IDs, **verbatim text** | This task | <= 1,500 |
| Interfaces | named `path:symbol` / line-range excerpts | This task | <= 1,500 |
| Baseline evidence | pre-edit `validate` output, trimmed | This task | <= 600 |
| Recovery detail | `RECOVERY.md` / `$recovery` skill | Only after a failure | on demand |

Each profile in `budgets.toml` caps the packet at a fraction of usable
context. The packet is about 20% of the window, leaving the rest for code
reads, tool output, reasoning and headroom.

## 2. Contract integrity rules (compiler-enforced)

1. Requirement text is copied byte-for-byte from the spec, with its ID
   and hash. It is never summarized.
2. Every cited ID must exist, be `approved`, and match the hash pinned
   in the task (otherwise lint fails until it is re-pinned or retired).
3. Mandatory sections are never truncated. If they exceed their cap or
   the packet exceeds the profile budget, the compiler exits non-zero
   with `SPLIT_REQUIRED`.
4. The packet ends with the integrity notice: requirements omitted from
   the packet remain in force, and a conflict means BLOCKED.
5. The packet manifest (`packet.json`) records the source file hashes,
   token counts per section and the compiler version. It is stored with
   the run for auditing.

## 3. Execution (run_worker.py)

```
lint task (pins, status, deps merged) -> compile packet -> CLAIM task/<ID>
  -> BASELINE gate -> codex exec (fresh session, hermetic, budgeted)
  -> RED/GREEN gates re-run by harness -> GUARD gate -> REPORT gate
  -> ledger entry -> (DONE: branch ready for review | BLOCKED: escalate)
```

The harness never trusts the model's claims. It re-runs the acceptance
tests and guards itself, and a mismatch between the claim and the
harness result is recorded as `REPORT_MISMATCH`, which counts as a
failure.

## 4. Handoff record

After every task, one JSON file goes to `status/ledger/` (schema:
`schemas/ledger-entry.schema.json`): task ID, status, base and result
commits, packet hash, requirement IDs covered, gate results, attempts,
token and time usage, blocker, and next dependency. The next task starts
from a freshly compiled packet. Nothing carries over in model memory.

## 5. Split rules (for the ARCHITECT)

Split a task when the packet exceeds budget, when it touches more than
one package, when it has more than about 3 acceptance tests, or when it
cites more than about 6 requirements. Split at a verifiable boundary: an
artifact contract, a public function, or a CLI. Each half must have its
own acceptance test.
