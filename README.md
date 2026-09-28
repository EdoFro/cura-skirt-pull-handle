# Cura Skirt Pull Handle

A post-processing script for UltiMaker Cura that adds non-planar pull handles
to skirts, making them easier to remove from the build plate. It can also
connect the skirt to the first layer to help remove aborted prints.

> [!WARNING]
> This project modifies XYZ toolpaths and extrusion. Always inspect the
> resulting G-code and supervise your first test prints.

## Demo

https://github.com/user-attachments/assets/67768322-29d1-4065-85c8-b1c94a7ff359

[▶ Watch the skirt pull-handle demo](docs/media/skirt-pull-handle-demo.mp4)

The video shows a printed handle being used to lift and remove the skirt from
the build plate.

## Features

- One pull handle on the top layer of each independent skirt.
- Support for sequential printing and curved skirts.
- Optional early handle on the outer loop of the first layer.
- Optional connector between the skirt and the model.
- Restoration of the previous fan state after printing a handle.
- Cura configuration interface and command-line mode for development.

## Tested compatibility

- UltiMaker Cura 5.12.
- Marlin G-code.
- Relative extrusion (`M83`).
- PETG with 1.75 mm filament and a 0.5 mm nozzle as the initial tested profile.

Other materials and nozzle diameters may work, but have not yet been validated.

## Installing in Cura

1. Download `SkirtPullHandle.py`.
2. In Cura, open **Help → Show Configuration Folder**.
3. Close Cura completely.
4. Copy the file into the `scripts` subfolder.
5. Open Cura again.
6. Go to **Extensions → Post Processing → Modify G-Code**.
7. Select **Add a script**, then choose **Skirt Pull Handle**.

When upgrading, remove the previous instance from the post-processing dialog
and add it again so Cura loads the new settings.

## Default settings

- Path length between anchors: 10 mm.
- Outward reach: 5 mm.
- Programmed height: 3 mm.
- Speed: 12 mm/s.
- Fan speed while printing the handle: 75%.
- Flow at the arrival anchor: gradually increased up to 140%.
- Early handle: disabled.
- Skirt-to-model connector: disabled; maximum length 30 mm.

If a loop is too short, its anchors are too close together, or its handle would
leave the build plate, that skirt is skipped and a warning is added to the
G-code.

## Command line

```powershell
python .\add_skirt_handle.py input.gcode output.gcode
```

```powershell
python .\add_skirt_handle.py input.gcode output.gcode `
  --add-early-handle `
  --connect-skirt-to-model
```

## Developing with VS Code

Open the repository root in VS Code. The project includes debugging profiles,
`unittest` discovery settings, and extension recommendations.

```powershell
python -m unittest discover -s tests -v
```

See the [development guide](docs/DEVELOPMENT.md) and
[contribution guidelines](CONTRIBUTING.md) for more information.

## License

This project is distributed under the [MIT License](LICENSE).

## Project status

Current version: **0.5.0 (alpha)**.
