# Contribuir

Los reportes de errores deberían incluir la versión de Cura, impresora,
firmware, modo de extrusión, ajustes del skirt y un G-code mínimo sin datos
sensibles.

Antes de enviar cambios:

```powershell
python -m py_compile .\SkirtPullHandle.py .\add_skirt_handle.py
python -m unittest discover -s tests -v
```

Los cambios de trayectorias deben probarse primero en un visor de G-code y
después mediante una impresión supervisada.
