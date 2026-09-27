#!/usr/bin/env python3
"""Add experimental non-planar pull handles to Cura skirt loops.

The input file is never overwritten unless input and output are explicitly the
same path. Version 0.3 supports relative extrusion (M83) and adds one handle to
the top layer of every spatially distinct skirt found in sequential printing.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

try:
    from ..Script import Script as CuraScript
except ImportError:
    # Allows command-line use and local tests outside Cura.
    CuraScript = object


MOVE_RE = re.compile(r"^\s*G([01])\b", re.IGNORECASE)
FIELD_RE = re.compile(r"(?:^|\s)([XYZEFS])(-?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)


class Move:
    def __init__(self, line_index, start_x, start_y, start_z, end_x, end_y, end_z, extrusion):
        self.line_index = line_index
        self.start_x = start_x
        self.start_y = start_y
        self.start_z = start_z
        self.end_x = end_x
        self.end_y = end_y
        self.end_z = end_z
        self.extrusion = extrusion

    @property
    def xy_length(self) -> float:
        return math.hypot(self.end_x - self.start_x, self.end_y - self.start_y)


class SkirtBlock:
    def __init__(self, start, end, moves):
        self.start = start
        self.end = end
        self.moves = moves

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [value for move in self.moves for value in (move.start_x, move.end_x)]
        ys = [value for move in self.moves for value in (move.start_y, move.end_y)]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def top_z(self) -> float:
        return max(max(move.start_z, move.end_z) for move in self.moves)


class HandleSpan:
    def __init__(
        self,
        start_move,
        end_move,
        start_x,
        start_y,
        end_x,
        end_y,
        z,
        start_offset,
        end_offset,
        e_per_mm,
    ):
        self.start_move = start_move
        self.end_move = end_move
        self.start_x = start_x
        self.start_y = start_y
        self.end_x = end_x
        self.end_y = end_y
        self.z = z
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.e_per_mm = e_per_mm


def fields(line: str) -> dict[str, float]:
    return {key.upper(): float(value) for key, value in FIELD_RE.findall(line)}


def find_skirt_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == ";TYPE:SKIRT":
            start = index + 1
        elif start is not None and (
            line.startswith(";TYPE:") or line.startswith(";LAYER:") or line.startswith(";MESH:")
        ):
            blocks.append((start, index))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    if not blocks:
        raise ValueError("No se encontró ningún bloque ;TYPE:SKIRT")
    return blocks


def same_skirt_footprint(a: SkirtBlock, b: SkirtBlock, tolerance: float = 1.0) -> bool:
    """Match repeated layers of one skirt without merging nearby objects."""
    amin_x, amin_y, amax_x, amax_y = a.bounds
    bmin_x, bmin_y, bmax_x, bmax_y = b.bounds
    acx, acy = (amin_x + amax_x) / 2, (amin_y + amax_y) / 2
    bcx, bcy = (bmin_x + bmax_x) / 2, (bmin_y + bmax_y) / 2
    return (
        math.hypot(acx - bcx, acy - bcy) <= tolerance
        and abs((amax_x - amin_x) - (bmax_x - bmin_x)) <= tolerance * 2
        and abs((amax_y - amin_y) - (bmax_y - bmin_y)) <= tolerance * 2
    )


def group_skirt_blocks(blocks: list[SkirtBlock]) -> list[list[SkirtBlock]]:
    groups: list[list[SkirtBlock]] = []
    for block in blocks:
        for group in groups:
            if same_skirt_footprint(block, group[0]):
                group.append(block)
                break
        else:
            groups.append([block])
    return groups


def extrusion_mode_at(lines: list[str], end: int) -> str:
    mode = "absolute"
    for line in lines[:end]:
        command = line.split(";", 1)[0].strip().upper()
        if command == "M82":
            mode = "absolute"
        elif command == "M83":
            mode = "relative"
    return mode


def fan_restore_command_at(lines: list[str], end: int) -> str:
    command = "M107"
    for line in lines[:end]:
        clean = line.split(";", 1)[0].strip().upper()
        if clean.startswith("M107"):
            command = "M107"
        elif clean.startswith("M106"):
            values = fields(clean)
            command = f"M106 S{fmt(values.get('S', 255), 0)}"
    return command


def parse_skirt_moves(lines: list[str], start: int, end: int) -> list[Move]:
    x = y = z = 0.0
    # Establish the machine position immediately before the skirt block.
    for line in lines[:start]:
        if MOVE_RE.match(line.split(";", 1)[0]):
            args = fields(line)
            x, y, z = args.get("X", x), args.get("Y", y), args.get("Z", z)

    moves: list[Move] = []
    for index in range(start, end):
        line = lines[index]
        if not MOVE_RE.match(line.split(";", 1)[0]):
            continue
        args = fields(line)
        nx, ny, nz = args.get("X", x), args.get("Y", y), args.get("Z", z)
        extrusion = args.get("E", 0.0)
        if extrusion > 0 and math.hypot(nx - x, ny - y) > 0:
            moves.append(Move(index, x, y, z, nx, ny, nz, extrusion))
        x, y, z = nx, ny, nz
    return moves


def skirt_loops(moves: list[Move]) -> list[list[Move]]:
    # Cura separates skirt loops with a non-extruding movement.
    if not moves:
        raise ValueError("El bloque SKIRT no contiene movimientos extruidos")
    starts = [0]
    for pos in range(1, len(moves)):
        if moves[pos].line_index > moves[pos - 1].line_index + 1:
            starts.append(pos)
    return [
        moves[start : starts[index + 1] if index + 1 < len(starts) else len(moves)]
        for index, start in enumerate(starts)
    ]


def point_on_loop(loop: list[Move], distance: float) -> tuple[Move, float, float, float]:
    walked = 0.0
    for move in loop:
        if walked + move.xy_length >= distance - 1e-9:
            offset = min(move.xy_length, max(0.0, distance - walked))
            ratio = offset / move.xy_length
            return (
                move,
                move.start_x + (move.end_x - move.start_x) * ratio,
                move.start_y + (move.end_y - move.start_y) * ratio,
                offset,
            )
        walked += move.xy_length
    move = loop[-1]
    return move, move.end_x, move.end_y, move.xy_length


def select_handle_span(
    moves: list[Move], path_length: float, min_chord: float, loop_position: str = "last"
) -> HandleSpan:
    loops = skirt_loops(moves)
    loop = loops[0] if loop_position == "first" else loops[-1]
    total = sum(move.xy_length for move in loop)
    if total < path_length + 2.0:
        raise ValueError("La última vuelta es demasiado corta para el asa")

    # Centre one fixed-length window on the loop. It may cross any number of
    # short or curved G1 moves; no curvature optimisation is attempted.
    start_distance = (total - path_length) / 2
    end_distance = start_distance + path_length
    start_move, start_x, start_y, start_offset = point_on_loop(loop, start_distance)
    end_move, end_x, end_y, end_offset = point_on_loop(loop, end_distance)
    if math.hypot(end_x - start_x, end_y - start_y) < min_chord:
        raise ValueError("Los anclajes quedarían demasiado cerca entre sí")

    total_e = sum(move.extrusion for move in loop)
    return HandleSpan(
        start_move,
        end_move,
        start_x,
        start_y,
        end_x,
        end_y,
        start_move.start_z,
        start_offset,
        end_offset,
        total_e / total,
    )


def fmt(value: float, digits: int = 3) -> str:
    if digits == 0:
        return f"{value:.0f}"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def build_span_replacement(
    span: HandleSpan,
    center_x: float,
    center_y: float,
    reach: float,
    height: float,
    segments: int,
    speed: float,
    fan_percent: float,
    landing_flow: float,
    bed_bounds: tuple[float, float, float, float],
    fan_restore_command: str,
) -> list[str]:
    dx, dy = span.end_x - span.start_x, span.end_y - span.start_y
    chord = math.hypot(dx, dy)
    tx, ty = dx / chord, dy / chord
    midpoint_x = (span.start_x + span.end_x) / 2
    midpoint_y = (span.start_y + span.end_y) / 2
    n1 = (-ty, tx)
    radial = (midpoint_x - center_x, midpoint_y - center_y)
    outward = n1 if n1[0] * radial[0] + n1[1] * radial[1] >= 0 else (-n1[0], -n1[1])

    def fits_bed(normal: tuple[float, float]) -> bool:
        min_x, min_y, max_x, max_y = bed_bounds
        for sample in range(25):
            t = sample / 24
            wave = math.sin(math.pi * t)
            px = span.start_x + dx * t + normal[0] * reach * wave
            py = span.start_y + dy * t + normal[1] * reach * wave
            if not (min_x <= px <= max_x and min_y <= py <= max_y):
                return False
        return True

    if fits_bed(outward):
        nx, ny = outward
    elif fits_bed((-outward[0], -outward[1])):
        nx, ny = -outward[0], -outward[1]
    else:
        raise ValueError("No hay espacio en la cama para colocar el asa")

    output = [";SKIRT_HANDLE_BEGIN v0.5"]
    if span.start_offset > 1e-6:
        start_rate = span.start_move.extrusion / span.start_move.xy_length
        output.append(
            f"G1 X{fmt(span.start_x)} Y{fmt(span.start_y)} Z{fmt(span.z)} "
            f"E{fmt(span.start_offset * start_rate, 5)}"
        )
    fan_pwm = round(255 * fan_percent / 100)
    output.append(f"M106 S{fan_pwm} ; skirt handle cooling ({fmt(fan_percent, 0)}%)")

    previous = (span.start_x, span.start_y, span.z)
    for step in range(1, segments + 1):
        t = step / segments
        wave = math.sin(math.pi * t)
        point = (
            span.start_x + dx * t + nx * reach * wave,
            span.start_y + dy * t + ny * reach * wave,
            span.z + height * wave,
        )
        descent = max(0.0, (t - 0.5) * 2.0)
        flow = 1.0 + (landing_flow - 1.0) * descent
        command = (
            f"G1 X{fmt(point[0])} Y{fmt(point[1])} Z{fmt(point[2])} "
            f"E{fmt(math.dist(previous, point) * span.e_per_mm * flow, 5)}"
        )
        if step == 1:
            command += f" F{fmt(speed * 60, 0)}"
        output.append(command)
        previous = point

    suffix = span.end_move.xy_length - span.end_offset
    if suffix > 1e-6:
        end_rate = span.end_move.extrusion / span.end_move.xy_length
        output.append(
            f"G1 X{fmt(span.end_move.end_x)} Y{fmt(span.end_move.end_y)} "
            f"Z{fmt(span.end_move.end_z)} E{fmt(suffix * end_rate, 5)} F1200"
        )
    else:
        output.append("G1 F1200")
    output.append(f"{fan_restore_command} ; restore previous fan state")
    output.append(";SKIRT_HANDLE_END")
    return output


def find_first_model_anchor(lines: list[str], start: int) -> tuple[float, float, float] | None:
    x = y = z = 0.0
    for line in lines[:start]:
        if MOVE_RE.match(line.split(";", 1)[0]):
            values = fields(line)
            x, y, z = values.get("X", x), values.get("Y", y), values.get("Z", z)

    mesh_seen = False
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith(";LAYER:") and mesh_seen:
            return None
        if stripped.startswith(";MESH:") and stripped != ";MESH:NONMESH":
            mesh_seen = True
        if not MOVE_RE.match(line.split(";", 1)[0]):
            continue
        values = fields(line)
        nx, ny, nz = values.get("X", x), values.get("Y", y), values.get("Z", z)
        if mesh_seen and values.get("E", 0.0) > 0 and math.hypot(nx - x, ny - y) > 0:
            return x, y, z
        x, y, z = nx, ny, nz
    return None


def build_model_connector(block: SkirtBlock, target: tuple[float, float, float], speed: float) -> list[str]:
    source = block.moves[-1]
    distance = math.hypot(target[0] - source.end_x, target[1] - source.end_y)
    loop = skirt_loops(block.moves)[-1]
    e_per_mm = sum(move.extrusion for move in loop) / sum(move.xy_length for move in loop)
    return [
        ";SKIRT_MODEL_CONNECTOR_BEGIN v0.5",
        f"G1 X{fmt(target[0])} Y{fmt(target[1])} Z{fmt(source.end_z)} "
        f"E{fmt(distance * e_per_mm, 5)} F{fmt(speed * 60, 0)}",
        ";SKIRT_MODEL_CONNECTOR_END",
    ]


def transform(text: str, args: argparse.Namespace) -> tuple[str, int, list[str]]:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    raw_blocks = find_skirt_blocks(lines)
    blocks: list[SkirtBlock] = []
    for start, end in raw_blocks:
        if extrusion_mode_at(lines, start) != "relative":
            raise ValueError("Skirt Pull Handle requiere extrusión relativa (M83)")
        moves = parse_skirt_moves(lines, start, end)
        if moves:
            blocks.append(SkirtBlock(start, end, moves))
    if not blocks:
        raise ValueError("Los bloques SKIRT no contienen movimientos extruidos")

    groups = group_skirt_blocks(blocks)
    changes: list[tuple[int, int, list[str]]] = []
    warnings: list[str] = []
    handle_count = 0
    connector_count = 0
    for group in groups:
        first_block = min(group, key=lambda block: (block.top_z, block.start))
        top_block = max(group, key=lambda block: (block.top_z, block.start))
        handle_jobs = [(top_block, "last")]
        if args.add_early_handle:
            if first_block is top_block:
                handle_jobs = [(first_block, "first")]
            else:
                handle_jobs.append((first_block, "first"))

        for block, loop_position in handle_jobs:
            try:
                span = select_handle_span(
                    block.moves, args.anchor_spacing, args.min_chord, loop_position
                )
                min_x, min_y, max_x, max_y = block.bounds
                replacement = build_span_replacement(
                    span,
                    (min_x + max_x) / 2,
                    (min_y + max_y) / 2,
                    args.reach,
                    args.height,
                    args.segments,
                    args.speed,
                    args.fan_percent,
                    args.landing_flow,
                    (args.bed_min_x, args.bed_min_y, args.bed_max_x, args.bed_max_y),
                    fan_restore_command_at(lines, span.start_move.line_index),
                )
                changes.append((span.start_move.line_index, span.end_move.line_index, replacement))
                handle_count += 1
            except ValueError as error:
                warnings.append(f"Skirt cerca de línea {block.start}: {error}")

        if args.connect_skirt_to_model:
            target = find_first_model_anchor(lines, first_block.end)
            if target is None:
                warnings.append(f"Skirt cerca de línea {first_block.start}: no se encontró la pieza")
            else:
                source = first_block.moves[-1]
                distance = math.hypot(target[0] - source.end_x, target[1] - source.end_y)
                if distance > args.max_connector_length:
                    warnings.append(
                        f"Skirt cerca de línea {first_block.start}: tirante de {distance:.1f} mm omitido"
                    )
                elif distance > 0.1:
                    connector = build_model_connector(first_block, target, args.connector_speed)
                    insert_at = source.line_index + 1
                    changes.append((insert_at, insert_at - 1, connector))
                    connector_count += 1

    for start_line, end_line, replacement in sorted(changes, reverse=True):
        lines[start_line : end_line + 1] = replacement
    if connector_count:
        lines.insert(0, f";SKIRT_MODEL_CONNECTORS: {connector_count}")
    if handle_count:
        lines.insert(0, f";SKIRT_PULL_HANDLES: {handle_count}")
    return newline.join(lines) + newline, handle_count, warnings


def process(source: Path, destination: Path, args: argparse.Namespace) -> None:
    text = source.read_text(encoding="utf-8")
    transformed, handle_count, warnings = transform(text, args)
    destination.write_text(transformed, encoding="utf-8", newline="")
    print(f"Creado: {destination}")
    print(f"Asas agregadas: {handle_count}")
    for warning in warnings:
        print(f"ADVERTENCIA: {warning}")


class SkirtPullHandle(CuraScript):
    """Cura PostProcessingPlugin entry point."""

    def getSettingDataString(self):
        return r'''{
            "name": "Skirt Pull Handle",
            "key": "SkirtPullHandle",
            "metadata": {},
            "version": 2,
            "settings": {
                "add_early_handle": {
                    "label": "Agregar asa temprana",
                    "description": "Añade un asa a la vuelta exterior de la primera capa del skirt.",
                    "type": "bool", "default_value": false
                },
                "connect_skirt_to_model": {
                    "label": "Conectar skirt con la pieza",
                    "description": "Extruye un tirante desde el skirt hasta el primer punto de la pieza en la primera capa.",
                    "type": "bool", "default_value": false
                },
                "anchor_spacing": {
                    "label": "Recorrido entre anclajes",
                    "description": "Longitud recorrida sobre el skirt que será reemplazada por el asa.",
                    "unit": "mm", "type": "float", "default_value": 10.0,
                    "minimum_value": 6.0
                },
                "reach": {
                    "label": "Salida lateral",
                    "description": "Distancia máxima que el asa se proyecta hacia fuera del skirt.",
                    "unit": "mm", "type": "float", "default_value": 5.0,
                    "minimum_value": 1.0
                },
                "height": {
                    "label": "Altura programada",
                    "description": "Altura máxima programada sobre la capa superior del skirt.",
                    "unit": "mm", "type": "float", "default_value": 3.0,
                    "minimum_value": 1.0
                },
                "speed": {
                    "label": "Velocidad del asa",
                    "description": "Velocidad de los movimientos de extrusión no planar del asa.",
                    "unit": "mm/s", "type": "float", "default_value": 12.0,
                    "minimum_value": 1.0
                },
                "fan_percent": {
                    "label": "Ventilador durante el asa",
                    "description": "Potencia temporal del ventilador mientras se imprime el asa.",
                    "unit": "%", "type": "int", "default_value": 75,
                    "minimum_value": 0, "maximum_value": 100
                },
                "landing_flow_percent": {
                    "label": "Flujo en anclaje de llegada",
                    "description": "Refuerzo gradual de flujo aplicado al extremo de llegada.",
                    "unit": "%", "type": "int", "default_value": 140,
                    "minimum_value": 100, "maximum_value": 250
                },
                "max_connector_length": {
                    "label": "Longitud máxima del tirante",
                    "description": "Omite la conexión con la pieza cuando el viaje supera esta distancia.",
                    "unit": "mm", "type": "float", "default_value": 30.0,
                    "minimum_value": 1.0
                },
                "bed_max_x": {
                    "label": "Máximo X de la cama",
                    "description": "Coordenada X máxima permitida para mantener el asa dentro de la cama.",
                    "unit": "mm", "type": "float", "default_value": 220.0
                },
                "bed_max_y": {
                    "label": "Máximo Y de la cama",
                    "description": "Coordenada Y máxima permitida para mantener el asa dentro de la cama.",
                    "unit": "mm", "type": "float", "default_value": 220.0
                }
            }
        }'''

    def execute(self, data):
        args = argparse.Namespace(
            add_early_handle=bool(self.getSettingValueByKey("add_early_handle")),
            connect_skirt_to_model=bool(self.getSettingValueByKey("connect_skirt_to_model")),
            anchor_spacing=float(self.getSettingValueByKey("anchor_spacing")),
            min_chord=5.0,
            reach=float(self.getSettingValueByKey("reach")),
            height=float(self.getSettingValueByKey("height")),
            segments=24,
            speed=float(self.getSettingValueByKey("speed")),
            fan_percent=float(self.getSettingValueByKey("fan_percent")),
            landing_flow=float(self.getSettingValueByKey("landing_flow_percent")) / 100.0,
            max_connector_length=float(self.getSettingValueByKey("max_connector_length")),
            connector_speed=20.0,
            bed_min_x=0.0,
            bed_min_y=0.0,
            bed_max_x=float(self.getSettingValueByKey("bed_max_x")),
            bed_max_y=float(self.getSettingValueByKey("bed_max_y")),
        )
        try:
            transformed, count, warnings = transform("".join(data), args)
        except ValueError as error:
            data[0] = f";SKIRT_PULL_HANDLE_WARNING: {error}\n" + data[0]
            return data
        notes = f";SKIRT_PULL_HANDLE: {count} handle(s) added"
        if warnings:
            notes += "; " + " | ".join(warnings)
        return [notes + "\n" + transformed]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--anchor-spacing", type=float, default=10.0)
    parser.add_argument("--add-early-handle", action="store_true")
    parser.add_argument("--connect-skirt-to-model", action="store_true")
    parser.add_argument("--min-chord", type=float, default=5.0)
    parser.add_argument("--reach", type=float, default=5.0)
    parser.add_argument("--height", type=float, default=3.0)
    parser.add_argument("--segments", type=int, default=24)
    parser.add_argument("--speed", type=float, default=12.0, help="mm/s")
    parser.add_argument("--fan-percent", type=float, default=75.0)
    parser.add_argument(
        "--landing-flow",
        type=float,
        default=1.4,
        help="multiplicador de flujo al llegar al segundo anclaje",
    )
    parser.add_argument("--bed-min-x", type=float, default=0.0)
    parser.add_argument("--bed-min-y", type=float, default=0.0)
    parser.add_argument("--bed-max-x", type=float, default=220.0)
    parser.add_argument("--bed-max-y", type=float, default=220.0)
    parser.add_argument("--max-connector-length", type=float, default=30.0)
    parser.add_argument("--connector-speed", type=float, default=20.0)
    args = parser.parse_args()
    if args.segments < 4 or min(args.anchor_spacing, args.reach, args.height, args.speed) <= 0:
        parser.error("Los parámetros geométricos deben ser positivos y segments >= 4")
    if not 0 <= args.fan_percent <= 100:
        parser.error("fan-percent debe estar entre 0 y 100")
    if args.landing_flow < 1:
        parser.error("landing-flow debe ser mayor o igual a 1")
    process(args.input, args.output, args)


if __name__ == "__main__":
    main()
