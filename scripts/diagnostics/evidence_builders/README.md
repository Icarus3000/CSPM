# Preserved clean-room evidence builders

These first-party helpers were recovered during the October 9, 2026 computer
closeout. Their originals remain unchanged in ignored `outputs/` directories.
Only helper source is preserved here; private raw results, captures, workbooks,
settings, manifests and logs remain on the original computer. Committed reports
under `docs/` are the continuation record on a fresh clone.

| Preserved folder | Original ignored folder | Purpose |
| --- | --- | --- |
| `native_wait_20261008` | `outputs/native_wait_20261008` | Historical source-band report and shared allowlist helpers |
| `created_band_resume_20261008` | `outputs/created_band_resume_20261008` | Source-band continuation, moving/safety reports, public-evidence validation and the existing-selector fallback launcher |
| `native_cleanroom` | `outputs/native_cleanroom` | October 4 physical-qualification collector |

Preservation changes only repository-root discovery and helper dependency
lookups. The physical collector's old hard-coded profile identifier in its
privacy check is replaced with the current home-profile name. The source-band
constructor's introductory description now describes local evidence rather
than its original private scratch location. Original hashes and copy hashes
are retained in `SOURCE_PROVENANCE.json`. These SHA-256 values describe the
closeout's working-copy bytes; Git line-ending conversion can change those bytes
on another platform without changing the reviewed source.

The October 8 dependency chain is `moving_report.py` → `extend_report.py` →
`created_band_report_constructor.py`. Helpers continue to read the original
ignored evidence hierarchy under repository `outputs/` and `logs/`; relocating
source does not change raw-result or published-evidence identities. A fresh
clone does not contain those inputs. Dependencies on governed
`scripts/diagnostics/native_call_contract.py` are unchanged.

The builders write dated reports when run. Some use top-level statements and
must not be imported casually. The physical collector also reconstructs its
historical Markdown report; subsequent manually documented findings would
need preservation before rerunning it. These are preserved historical tools,
not an automatic regeneration or publication pipeline. Review generated diffs
and run the repository's privacy checks before staging any output.

For later authorized local evidence review, from the repository root and with
the matching original private inputs present:

```powershell
python -B scripts/diagnostics/evidence_builders/created_band_resume_20261008/extend_report.py
python -B scripts/diagnostics/evidence_builders/created_band_resume_20261008/moving_report.py
python -B scripts/diagnostics/evidence_builders/created_band_resume_20261008/safety_report.py
python -B scripts/diagnostics/evidence_builders/created_band_resume_20261008/validate_public.py
```

`existing_safety_launcher.py` is a preserved disposable runtime launcher, not a
report builder. It requires an explicitly owned Y: output directory in
`CSPM_EXISTING_SAFETY_RUN_DIR`, and remains governed by the original desktop
validation and protected-data boundaries. No launcher or builder was executed
during preservation. The seven Python copies were checked with AST parsing and
in-memory compilation only; no WebEngine, native window, build or animation
experiment was launched.

The candidate remains unqualified. The collector-free Productivity restore
deadline failure and three retained Home pixel failures remain recorded in
`docs/CLEANROOM_CREATED_BAND_MOVING_2026-10-08.md`. Preserving these tools does
not authorize packaging, installation or production promotion.
