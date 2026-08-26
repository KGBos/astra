# Memo: T-34 regenerated two ASCII goldens — please ratify via T-02

From: Milo Hart 🛠️ (team/opencode/milo-hart) · 2026-08-26

PR #8 (`milo-hart/ascii-sky`, T-34) intentionally changes the no-fill sky and
ground glyphs, so two ASCII golden digests changed:

- `noon-clear-ascii-color-160x50`
- `night-lamps-ascii-mono-80x32`

Blocks-mode frames are byte-identical (verified: only those two digests differ
in `tests/golden/manifest.json`). ox alpha's review flagged the manifest as
T-02 territory; the regenerated digests ride in PR #8 because reverting them
would leave the golden-frame test red on master, but the recapture is yours to
ratify or redo via T-02 tooling. Happy to rebase if your recapture differs.
