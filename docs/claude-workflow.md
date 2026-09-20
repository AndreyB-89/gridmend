# How we use Claude Code / Codex tonight

Everyone's agent reads `CLAUDE.md` (Codex reads the same file through `AGENTS.md`). The task order is in [build-plan.md](build-plan.md).

## One session per owner, separate branches

| Person | Branch | Start prompt |
| --- | --- | --- |
| Mortaza | `feat/api-web` | "Do build-plan task 1 (FastAPI skeleton with MOCK responses matching contracts/types.ts v3), then task 4 (web UI) against the mocks. Then task 5 (SLNG) with the provider-adapter skill." |
| Valentin | `feat/cad-fit` | "Do build-plan task 2 (CadQuery ring template + missing segment + 5 checks, with pytest), then task 3 (homography + circle fit + overlay) on the demo photo. Keep functions free of HTTP." |
| Andrii | none (docs/evidence) | Measure the card with a ruler. Save the clicks for the demo photo in `fixtures/demo-clicks.json` (4 card corners, 5+ outer points, 5+ inner points, in pixels of the original image). Run the smoke test on main every 30 minutes. |

If one person runs two Claude sessions at once, use a git worktree per session (`claude --worktree` or `git worktree add ../gridmend-cad feat/cad-fit`). Two sessions must never edit the same checkout.

Merge small pieces to `main` often. Before merging, run the `smoke-test` skill.

## Loops

`/loop` repeats a prompt on a timer inside a session. Use these:

| When | Command | Why |
| --- | --- | --- |
| 20:15–22:05, one session on `main` | `/loop 20m /smoke-test` | Finds a broken `main` within 20 minutes. |
| While waiting for a teammate's piece | `/loop 15m git fetch; if origin/main changed, pull, run the smoke-test skill and tell me what is new or broken` | You integrate as soon as their slice lands. |
| After 22:05 (freeze) | `/loop 30m check git log since 22:05 on main; list any commit that adds an endpoint, dependency, provider or UI flow; then run the smoke-test skill` | Protects the freeze. |
| Galtea runs | `/loop 10m check the Galtea run status; when finished, save results with the save-evidence skill and stop the loop` | Evaluations are slow; don't watch them by hand. |

Stop a loop when its job is done. Don't leave loops running overnight (no work between 23:00 and 09:00).

## Good prompts

- "Implement X. Done when: <command> prints <result>. Run it and show me the output."
- "Replace the MOCK in `engine/providers/nebius.py` with a LIVE call using the provider-adapter skill. Keep the MOCK path for when there's no key."
- "Review my diff against CLAUDE.md hard rules only. List violations, nothing else."

## Bad prompts (they cost time)

- "Make it better" / "Add auto edge detection" before all Must tasks pass.
- Asking the agent to write CadQuery code at runtime from an LLM (rule 2).
- Letting the agent "fix" a failing Galtea case before the baseline is saved.
