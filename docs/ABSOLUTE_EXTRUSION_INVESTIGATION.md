# Absolute-extrusion (`M82`) support investigation

Date: 2026-09-27
Scope: design investigation only; this document does **not** enable `M82` input.

## Conclusion

The current implementation cannot safely process a skirt while `M82` is
active. It correctly rejects that input, and the rejection must stay in place
until extrusion state is modelled explicitly.

Supporting the usual Cura/Marlin `M82` output is feasible, but it is not a
one-line mode switch. The safest implementation is to calculate the original
absolute E coordinates, print the injected geometry temporarily in `M83`, then
restore the original logical E coordinate with `G92 E...`. It must be
introduced together with state-aware parsing and regression fixtures.

`G92 E...` changes the extruder's reported coordinate without commanding an
extrusion; Marlin documents `E` as a supported `G92` axis. [Marlin G92
reference](https://marlinfw.org/docs/gcode/G092.html)  `M82` and `M83` select
absolute and relative E positioning, respectively. [Marlin G-code
index](https://marlinfw.org/meta/gcode/)

## What the code does now

| Location | Current behaviour | Why it fails for `M82` |
| --- | --- | --- |
| `extrusion_mode_at` | Scans commands before each skirt and returns the last `M82`/`M83`. | `transform` rejects any skirt whose starting mode is not relative. It does not create an extrusion-state model. |
| `parse_skirt_moves` | Saves raw `E` as `Move.extrusion`; an E greater than zero marks a deposited move. | In `M82`, raw E is an endpoint, not material for that move. The required amount is `E_end - E_start`; a retraction can have a positive E endpoint. |
| `select_handle_span` | Sums raw E values to derive `e_per_mm`. | Absolute endpoints make the flow estimate grow with the file's E coordinate rather than the amount deposited. |
| `build_span_replacement` | Emits all inserted `E` values as deltas and replaces a range of original G1 lines. | Those deltas are interpreted as absolute coordinates under `M82`; without correction the next original E move becomes an unintended large retract or prime. |
| `build_model_connector` | Emits a delta E immediately after a skirt move. | It has the same absolute/relative mismatch and leaves downstream E state wrong. |

The implementation currently has no tracker for E coordinates, `G92 E...`,
active tool, or an E value at the start/end of a `Move`. This is intentional
and appropriate for its documented `M83`-only scope.

## Recommended implementation approach

Introduce a single ordered modal scan used by both skirt detection and anchor
lookup. For each line, record at least:

- extrusion mode (`M82` or `M83`);
- active tool (`Tn`), with a separately tracked E coordinate per tool;
- the E coordinate before and after every `G0`/`G1` containing E;
- deposited delta (`E_end - E_start` in absolute mode, raw E in relative
  mode); and
- explicit `G92 E...` resets.

`Move` should carry `e_start`, `e_end`, and `e_delta`; selection and flow math
must use only `e_delta`. A move is deposited only when `e_delta > 0` and it
has XY length.

For an absolute-mode handle replacement, do not rewrite the remainder of the
file. Emit this conceptual sequence, using the original `e_end` from the last
replaced movement:

```gcode
M83                         ; temporary relative E for generated geometry
G1 ... E<delta>             ; optional partial original segment
G1 ... E<delta>             ; handle segments
G1 ... E<delta>             ; optional final original segment
M82                         ; restore the mode that was active at insertion
G92 E<original end E>       ; restore the coordinate expected by next line
```

The connector receives the same wrapper, except its restoration target is the
E endpoint of the source skirt move. This preserves the original downstream
logical state while retaining the deliberately extra physical filament in the
handle or connector.

Example: if the replaced original path ended at `E102.000`, the generated
relative moves can add 1.5 mm of extra material and the code then executes
`G92 E102.000`. A following original `G1 E101.200` remains the intended
0.8-mm retract. A following `G1 E102.400` remains a 0.4-mm prime/deposit.

### Why this is preferable to rewriting later absolute E values

Rewriting every following E value by the inserted-material delta must continue
until the next `G92 E`, handle negative retractions, account for tool changes,
and be repeated for every injection. Overlapping edits and Cura's frequent E
resets make that approach brittle. The local `M83`/`M82` wrapper plus `G92`
contains the state correction to the injected block and leaves original lines
byte-for-byte intact afterward.

Generating absolute E values directly would still need the same final `G92`
restore, while requiring more bookkeeping and numeric formatting. The
temporary-relative wrapper therefore has the smaller and clearer failure
surface for the Marlin compatibility target.

## Required guards and compatibility boundaries

- Treat an `M82`/`M83`, `G92 E`, or `Tn` inside a G1 range being replaced as a
  hard skip with a warning unless range splitting has been explicitly
  implemented. The current replacement deletes every line between its anchor
  moves, so silently crossing modal state changes is unsafe in either mode.
- The state scan must process Cura layer `G92 E0` commands in order. A reset
  before a skirt establishes its starting E; a reset after an injected block
  remains correct because the injected `G92` first restores the original
  expected coordinate.
- Retractions need no special transformation when their original coordinates
  are restored. They do need tests: absolute retractions are decreasing E
  coordinates, not negative raw E fields.
- Sequential printing uses multiple spatially grouped skirt blocks. Every
  handle and connector must capture its own original E endpoint; no state may
  leak from the first object to the second.
- Multi-extruder G-code needs active-tool-aware E tracking and an explicit
  support decision. `T0`, `T1`, etc. select physical or virtual tools in
  Marlin. [Marlin tool-selection reference](https://marlinfw.org/docs/gcode/T.html)
  Initial support should be limited to a stable active tool throughout each
  injected region. Reject a tool change inside a skirt or between a connector
  source and its insertion point; add cross-tool tests before claiming general
  multi-extruder support.
- This analysis assumes normal `G0`/`G1` E extrusion. Firmware retracts
  (`G10`/`G11`), macro-driven extrusion, mixing/duplication modes, and
  non-Marlin firmware should remain outside the initial compatibility claim.

## Acceptance criteria for a future implementation

1. Existing `M83` fixtures remain byte-for-byte equivalent outside injected
   ranges and all current tests pass.
2. A minimal all-`M82` fixture with `G92 E0` before the skirt produces a handle
   whose generated E moves are inside a temporary `M83`/`M82` wrapper and whose
   final `G92 E` equals the original last replaced move's E endpoint.
3. An all-`M82` fixture with a retraction and prime immediately after the
   handle verifies their physical deltas match the unmodified file.
4. A layer-reset fixture verifies a pre-skirt reset, a post-handle reset, and
   the next layer's extrusion all retain their original semantics.
5. The existing two-object sequential-print fixture is converted to valid
   absolute E coordinates (not merely by swapping `M83` to `M82`) and verifies
   one restoration per handle and per connector with no cross-object leakage.
6. A two-tool fixture verifies per-tool E bookkeeping or, until that support is
   implemented, a clear warning and no transformation when a relevant tool
   change is present.
7. Tests cover `G92 E`, `M82`/`M83`, and `Tn` inside a would-be replacement
   range and assert that the script skips the unsafe handle rather than
   deleting modal commands.
8. At least one supervised Marlin test print validates the handle, connector,
   retraction after it, and the next layer before the README advertises `M82`
   compatibility.

## Verification performed for this investigation

- Read the parser, selection, generation, connector, grouping, and replacement
  paths in `SkirtPullHandle.py`.
- Inspected both fixtures: they begin in absolute mode for priming, switch to
  `M83` before `;TYPE:SKIRT`, contain `G92 E0` resets, and the larger fixture
  contains two sequential objects.
- Attempted the repository test command. No Python interpreter or Python
  launcher is available in this workspace environment, so the existing suite
  could not be executed here. No production code was changed.
