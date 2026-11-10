# Movies history / recommendations: actual TDD evidence

Base `9d99d02117f025e36325a6c76f4d197ec4abb46a`; isolated worktree, no live deployment.
Each slice below was added to tests, executed RED, then implemented and executed
GREEN before moving to the next slice. No failing test was removed to make green.
Commands used `python3 -m unittest discover -s tests -p test_movie_history.py -q`
and the equivalent `test_movie_recommendations.py` pattern. Initial test used `-v`.

| Slice | Observed RED | Observed GREEN |
|---|---|---|
| Persist actual playback, schema allowlist and reload | `movie_history core is not implemented` | 1 test OK |
| Selection/invalid playback, literal IMDb IDs | 14 subtest failures: `True is not false` | 2 tests OK |
| Completion threshold, rewatch, stale timestamps | completion `False is not true` | 3 tests OK |
| Private storage and symlink refusal | directory mode `509 != 448` (decimal modes) | 4 tests OK |
| Atomic failure preservation | injected replace failure: `HistoryError not raised` | 5 tests OK |
| Bounded records/metadata | `max_records not found` in signature | 6 tests OK |
| Corrupt/oversized JSON, schema fail closed | 2 assertion failures and 4 parser/schema errors (expected missing error translation) | 7 tests OK |
| Clear only history, recover invalid JSON | clear method callable assertion false | 8 tests OK |
| Concurrent updates | lost records: `5 != 25` | 9 tests OK |
| Local deterministic genre recommendations | `recommendation core not implemented` | 1 recommendation test OK |
| Honest sparse/no-match fallback | `'history' != 'catalogue'` | 2 recommendation tests OK |
| Conflicting duplicates / malformed rows / limits | malformed history `NoneType is not subscriptable` | 3 recommendation tests OK |
| Maximum Unicode retention | output size `1983341 not less than or equal to 1048576` | 10 history tests OK |
| Invalid Unicode metadata | `UnicodeEncodeError` on lone surrogate | 10 history tests OK |

The malformed-input RED errors were missing production validation/translation,
not import, syntax or test-fixture errors. All new functions are exercised by
end-to-end module tests using actual temporary files. Only atomic failure injection
uses a mock (`os.replace` raises); real persistence and concurrent writers are used.

Full-suite executions:
- After initial roundtrip: **735 tests, 40.808s, OK** (734 existing + first new test).
- After 13 new core tests: **747 tests, 35.940s, OK**.
- Focused final Unicode fix: **10 history tests, 2.717s, OK** and
  **3 recommendation tests, 0.001s, OK**.
- Final full-suite rerun after Unicode validation: **747 tests, 41.032s, OK**.
- `mypy --follow-imports=skip --ignore-missing-imports` on both production modules:
  **Success: no issues found in 2 source files**.

Self-review found and corrected same-directory descriptor reuse for locked
read/modify/write and locked clear's check; tests remained green. Parent independent
review is still required; this document does not claim an independent approval or
native Kodi playback acceptance. Full-suite installer output concerns temporary
fixtures. Nothing installed, pushed, uploaded or changed in live Kodi/Format/media.
