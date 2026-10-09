# P5. README and publish readiness

**When:** Sat 10 Oct, 18:00 to 20:00 IST, or Sunday morning.
**Session:** any build session.

## Prompt (paste as is)

```text
Task: make the repo ready to go public. Do not touch results/, observations/, tools/arch/ or the generated figures.

1. README.md for the code, not the article: what the repo contains (two sentences, no claims about the book), prerequisites, the make commands in order, expected run time, how faults are injected and why client_ref exists, the hexagonal layout of each stack and how make arch checks it, known limitations (one machine, in-app fault hook, not production code), and a note that the code was generated with Claude Code and reviewed by the author, with the prompts in prompts/.
2. LICENSE is already MIT. Leave it as is.
3. Scan the repo for secrets, tokens, absolute paths and personal data. Report every hit; fix the code-side ones.
4. Check versions.md matches what is actually built; fix any gaps.
5. Optional: a CI workflow that runs make contract for each stack. Skip it if it would take more than 20 minutes.

Done when python3 tools/arch/check_hexagonal.py --all --complete passes: every file in the CLAUDE.md tree exists and nothing else does. Show me its output, the README diff and the scan results.
```

## Your final checks before making the repo public

- [ ] README makes no claims about the book; the article does that, with page numbers.
- [ ] `observations/` and `prompts/` are committed as they were used.
- [ ] `results/` holds only harness output, with host.json and the raw k6 summaries.
- [ ] `python3 tools/arch/check_hexagonal.py --all --complete` passes on a fresh clone.
- [ ] No credentials beyond local development defaults, labelled as such.
