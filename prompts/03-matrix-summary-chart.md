# P3. Run matrix, summary and chart

**When:** Sat 10 Oct, 12:00 to 14:00 IST. You run the full matrix yourself afterwards
(about 1 hour 45 minutes at the defaults).
**Session:** continue the P2 session, or start a new one.

## Prompt (paste as is)

```text
Read docs/exp3-spec.md, sections "Run matrix", "Output files" and "Chart".

Task:
1. make exp3-all: warm-up per stack (60 s, not measured), then the full matrix in a fixed order, scaling idle stacks to 0 replicas, writing results/exp3/host.json once. Make it resumable: skip runs already in runs.csv for the same git SHA.
2. make exp3-all DRY_RUN=1: print the planned runs and the estimated duration without running anything.
3. make summary: results/exp3/summary.csv exactly as the spec defines it.
4. make chart: figures/exp3_duplicates.py reads only summary.csv and writes figures/exp3_duplicates.svg as specified, with --input and --output arguments. Leave the title placeholder; I write the title.
5. figures/tests/test_exp3_duplicates.py runs the script as a subprocess on figures/tests/fixtures/exp3_summary_synthetic.csv, clearly labelled synthetic, writing into tmp_path. Never put sample data in results/.

Use only the files the CLAUDE.md tree lists for harness/, results/ and figures/.

Do not run the full matrix. Run DRY_RUN=1, then a smoke run with TOTAL=500 for one stack and both variants, then make summary and make chart against the fixture. Show me the outputs.
```

## Then you run

```text
make exp3-all
make summary
make chart
```

Check `dropped_iterations` is 0 in every row. If a stack misses the 20:00 cut line, record why
in the article and move it to post 2.
