# Desarrollo

## Diseño

`SkirtPullHandle.py` es autocontenido: Cura carga los scripts desde su carpeta
`scripts` y espera que el archivo y la clase se llamen `SkirtPullHandle`.
También contiene el núcleo de transformación para probarlo sin ejecutar Cura.
`add_skirt_handle.py` es solamente el lanzador de terminal.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Los fixtures cubren una pieza con skirt de una capa y dos piezas secuenciales
con skirts de dos capas. Guarda resultados manuales en `local-artifacts/`.

## Prueba por terminal

```powershell
python .\add_skirt_handle.py `
  ".\tests\fixtures\box-x2-skirt.gcode" `
  ".\local-artifacts\output.gcode" `
  --add-early-handle `
  --connect-skirt-to-model
```

## Prueba en Cura

1. Copiar `SkirtPullHandle.py` a la carpeta `scripts` de Cura.
2. Reiniciar Cura.
3. Eliminar y volver a agregar el script si cambió su esquema de opciones.
4. Revisar el G-code antes de imprimir.

## Preparar una versión

1. Ejecutar todas las pruebas.
2. Actualizar `pyproject.toml`, los marcadores G-code y `CHANGELOG.md`.
3. Verificar manualmente en las versiones de Cura declaradas compatibles.
4. Distribuir `SkirtPullHandle.py`, `README.md` y `LICENSE`.
