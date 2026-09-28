# Development

## Design

`SkirtPullHandle.py` is intentionally self-contained: Cura loads custom scripts
from its `scripts` directory and expects the file and class to be named
`SkirtPullHandle`. It also contains the transformation core so it can be tested
without running Cura. `add_skirt_handle.py` is only the command-line launcher.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The fixtures cover one model with a single-layer skirt and two sequentially
printed models with two-layer skirts. Store manual results in
`local-artifacts/`.

## Command-line test

```powershell
python .\add_skirt_handle.py `
  ".\tests\fixtures\box-x2-skirt.gcode" `
  ".\local-artifacts\output.gcode" `
  --add-early-handle `
  --connect-skirt-to-model
```

## Testing in Cura

1. Copy `SkirtPullHandle.py` into Cura's `scripts` directory.
2. Restart Cura.
3. Remove and add the script again if its settings schema changed.
4. Inspect the generated G-code before printing.

## Preparing a release

1. Run the full test suite.
2. Update `pyproject.toml`, the G-code markers, and `CHANGELOG.md`.
3. Test manually in every Cura version declared compatible.
4. Distribute `SkirtPullHandle.py`, `README.md`, and `LICENSE`.
