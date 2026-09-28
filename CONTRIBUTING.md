# Contributing

Bug reports should include the Cura version, printer model, firmware, extrusion
mode, relevant skirt settings, and a minimal G-code file that reproduces the
problem without containing sensitive information.

Before submitting changes, run:

```powershell
python -m py_compile .\SkirtPullHandle.py .\add_skirt_handle.py
python -m unittest discover -s tests -v
```

Toolpath changes should be inspected in a G-code viewer first and then tested
with a supervised print.
