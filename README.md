# Cura Skirt Pull Handle

Script de posprocesamiento para UltiMaker Cura que añade asas no planares al
`skirt`, facilitando su retirada de la cama. Opcionalmente conecta el skirt con
la primera capa para ayudar a retirar impresiones abortadas.

> [!WARNING]
> Este proyecto modifica trayectorias XYZ y extrusión. Revisa siempre el G-code
> resultante y realiza las primeras pruebas bajo supervisión.

## Demo



https://github.com/user-attachments/assets/67768322-29d1-4065-85c8-b1c94a7ff359



[▶ Watch the skirt pull-handle demo](docs/media/skirt-pull-handle-demo.mp4)

The video shows a printed handle being used to lift and remove the skirt from
the build plate.

## Características

- Una asa en la capa superior de cada skirt independiente.
- Compatibilidad con impresiones secuenciales y skirts curvos.
- Asa temprana opcional en la vuelta exterior de la primera capa.
- Tirante opcional entre skirt y pieza.
- Restauración del estado previo del ventilador.
- Interfaz de configuración en Cura y modo de terminal para desarrollo.

## Compatibilidad comprobada

- UltiMaker Cura 5.12.
- G-code Marlin.
- Extrusión relativa (`M83`).
- PETG de 1,75 mm y boquilla de 0,5 mm como perfil inicial probado.

Otros materiales y diámetros pueden funcionar, pero aún no están validados.

## Instalación en Cura

1. Descarga `SkirtPullHandle.py`.
2. En Cura abre **Ayuda → Mostrar carpeta de configuración**.
3. Cierra Cura completamente.
4. Copia el archivo en la subcarpeta `scripts`.
5. Abre Cura.
6. Ve a **Extensiones → Posprocesamiento → Modificar G-code**.
7. Pulsa **Añadir un script** y elige **Skirt Pull Handle**.

Al actualizar, elimina la instancia anterior del diálogo de posprocesamiento y
vuelve a agregarla para cargar las opciones nuevas.

## Valores iniciales

- Recorrido entre anclajes: 10 mm.
- Salida lateral: 5 mm.
- Altura programada: 3 mm.
- Velocidad: 12 mm/s.
- Ventilador durante el asa: 75 %.
- Flujo en el anclaje de llegada: hasta 140 %.
- Asa temprana: desactivada.
- Tirante skirt–pieza: desactivado; máximo 30 mm.

Si una vuelta es demasiado corta, los anclajes quedan demasiado cerca o el asa
sale de la cama, ese skirt se omite y se añade una advertencia al G-code.

## Terminal

```powershell
python .\add_skirt_handle.py entrada.gcode salida.gcode
```

```powershell
python .\add_skirt_handle.py entrada.gcode salida.gcode `
  --add-early-handle `
  --connect-skirt-to-model
```

## Desarrollo con VS Code

Abre la carpeta raíz en VS Code. El proyecto incluye configuraciones de
depuración, pruebas `unittest` y recomendaciones de extensiones.

```powershell
python -m unittest discover -s tests -v
```

Consulta [la guía de desarrollo](docs/DEVELOPMENT.md) y
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

Este proyecto se distribuye bajo la [licencia MIT](LICENSE).

## Estado

Versión actual: **0.5.0 (alpha)**.
