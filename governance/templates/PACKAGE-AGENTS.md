# <package name>

<!-- TEMPLATE for <package dir>/AGENTS.md, filled by the bootstrap skill.
Hard cap: governance/budgets.toml [always_on].package_agents_md_max_tokens
(default 300). The packet embeds this file verbatim for every task in
this package, so every line must earn its tokens. Delete this comment. -->

Owns: <one or two lines: what this package is responsible for>.
Does not own: <what it must not reimplement; name the owning package>.

- May import: <allowed_imports from specs/boundaries.toml, or "no
  workspace package">.
- <Each artifact contract it produces or consumes, by ART-ID, with
  the keys a consumer relies on.>
- <Traps: places where docs/README disagree with the code, so the
  worker trusts the code. One line each.>
- <Domain invariants specific to this package, citing REQ IDs.>
- Tests: `<command to run this package's tests>`.
