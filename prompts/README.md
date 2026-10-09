# Prompts used to build this repo

Every line of code in this repo was generated with Claude Code and reviewed by the author.
These are the prompts, in the order they were used. They are committed so readers can
reproduce the build as well as the results.

## Order

| # | File | When (IST) | Session |
| --- | --- | --- | --- |
| P0 | `00-observation.md` | Fri 17:00 | Empty folder outside the repo, auto memory off |
| P1 | `01-friday-python-and-harness.md` | Fri 18:00 to 23:00 | New, plan mode |
| P2 | `02-saturday-dotnet-java.md` | Sat 08:00 to 12:00 | New, plan mode |
| P3 | `03-matrix-summary-chart.md` | Sat 12:00 to 14:00 | Same or new |
| P4 | `04-independent-review.md` | Sat, before the full matrix | **New**, review only |
| P5 | `05-readme-and-publish.md` | Sat evening or Sun morning | Any |
| P6 | `06-stretch-mcp-tool.md` | Only if done by Sat 20:00 | New, plan mode |

## One-time setup (before P1)

1. Create an empty private repo folder and `git init`.
2. Copy in the starter files: `.gitignore`, `.gitattributes`, `CLAUDE.md`, `.claude/`, `docs/`, `prompts/`,
   `tools/`, `LICENSE`.
3. Make the hooks executable: `chmod +x .claude/hooks/*.sh`.
4. Make sure `jq` and Python 3.12 or later are installed; the hooks need them.
5. Run `python3 tools/arch/selftest.py`. It must report 114/114. It builds every stack from the
   folder tree in CLAUDE.md and checks that the complete tree passes and that every deliberate violation
   is caught: files outside the tree, listed files missing, layering, naming, folder-to-package
   mismatches and modified architecture tests. Then `python3 tools/arch/check_hexagonal.py --all` must
   pass on the starter files alone.
6. On Windows, run Claude Code inside WSL2 so the bash hooks and make targets work.
7. Commit: `chore: agent instructions, architecture gate, experiment spec and prompts`.
8. Start Claude Code at the repo root and check that it reports loading `CLAUDE.md` and the
   imported `docs/exp3-spec.md`. Try asking it to edit `results/x.csv` or `tools/arch/check_hexagonal.py`;
   the hook should block both. Then ask it to create `harness/helpers.py`; when it tries to finish, the
   Stop hook should block it with "not in the folder structure". Delete the file afterwards.

## How these files keep the agent honest

- `CLAUDE.md` holds the complete folder tree of the repo, the hexagonal layers and naming conventions, rules G0 to G8 and the honesty rules H1 to H4, and imports the spec. It is nearly 400 lines, well over the usual 200-line guidance, because the tree is spelled out file by file; if adherence slips, move rules into `.claude/rules/` rather than shortening the tree.
- `.claude/rules/naive-baseline.md` loads only when Claude Code touches naive files, and tells it not to "fix" the control group.
- `.claude/hooks/protect-files.sh` blocks direct edits to `results/`, `observations/`, `CLAUDE.md`, `.claude/` and `tools/arch/`. That is a hard block, not a request: the agent cannot edit its own rules or its grader.
- `.claude/hooks/arch-gate.sh` runs `tools/arch/check_hexagonal.py --all` every time Claude Code tries to finish a turn. The first failure blocks the finish and feeds the violations back; if it still fails on the next try, the turn ends with a warning telling you not to accept the task.
- `tools/arch/check_hexagonal.py` reads the tree between the `structure:begin` and `structure:end` markers in `CLAUDE.md` and enforces it: with `--all` (the Stop hook) no file may exist outside the tree; for one stack (`make arch`) every listed file must also exist; with `--all --complete` (before publishing) every listed file in the repo must exist. It also checks the hexagonal layers and naming conventions of each stack, without building anything. To allow a new file, the author adds it to the tree; the agent cannot.
- `tools/arch/templates/` holds each stack's architecture test (import-linter contracts, an ArchUnit test, a NetArchTest test). Claude Code copies them verbatim; the checker fails if a copy is missing or differs, so the agent cannot weaken its own tests.
- `.claude/settings.json` turns auto memory off for this project, so everything the agent knows is in the repo.

## When something breaks (fix prompt)

```text
Here is the failing command and its output:
<paste>
Find the root cause first and explain it in two or three sentences. Then propose the smallest fix.
Do not change docs/exp3-spec.md, contracts/tests or the harness to make it pass; if you think one of them is wrong, tell me why and wait.
```

## When a review finding comes back (from P4)

```text
Review finding: <paste one finding>
Confirm or refute it by reading the code and, where possible, writing a failing test first. If confirmed, make the smallest fix, show the test passing and run make contract for every affected stack.
```
