#!/usr/bin/env python3
"""Data-driven generator for the Drone Camp - Day 4 flight-system guide.

Content lives as structured data in PAGES; a single renderer turns it into a
self-contained HTML file, and Chrome headless prints that to PDF. Editing the
guide means editing data here, not hand-tweaking a binary PDF.

Usage:
    python build_day4.py            # writes HTML + PDF next to this script
    python build_day4.py --html     # HTML only (skip Chrome)

Every code block flagged validate=True is compile-checked so indentation and
syntax errors can never silently ship again.
"""
from __future__ import annotations

import base64
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML_OUT = HERE / "Drone_Camp_Day_4_Flight_System.html"
PDF_OUT = HERE / "Drone_Camp_Day_4_Flight_System.pdf"
FONT_DIR = HERE / "fonts"


def font_face_css():
    """Embed the Open Sans variable fonts so the PDF never falls back."""
    faces = []
    variants = [
        ("OpenSans.ttf", "normal"),
        ("OpenSans-Italic.ttf", "italic"),
    ]
    for fname, style in variants:
        path = FONT_DIR / fname
        if not path.exists():
            raise SystemExit(
                f"Missing font {path}. Open Sans is required and must not fall back."
            )
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            "@font-face{font-family:'Open Sans';"
            f"font-style:{style};font-weight:300 800;font-stretch:75% 100%;"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}"
        )
    return "\n".join(faces)

TAGLINE = "Trace the route before launch, then test one small change at a time."
CHAIN = "READ  →  TRACE  →  CODE  →  PREVIEW  →  FLIGHT CHECK"

# --------------------------------------------------------------------------- #
# Syntax highlighting (offline, no dependencies)
# --------------------------------------------------------------------------- #
KEYWORDS = {
    "def", "return", "if", "elif", "else", "for", "in", "while", "import",
    "from", "and", "or", "not", "is", "True", "False", "None", "pass",
    "break", "continue", "with", "as", "class", "lambda",
}
BUILTINS = {"range", "print", "int", "input", "len", "str", "float", "abs"}

_TOKEN_RE = re.compile(
    r"""
    (?P<com>\#[^\n]*) |
    (?P<str>[frbFRB]{0,2}"(?:\\.|[^"\\])*" | [frbFRB]{0,2}'(?:\\.|[^'\\])*') |
    (?P<num>\b\d+\b) |
    (?P<name>[A-Za-z_]\w*) |
    (?P<ws>[ \t]+) |
    (?P<other>.)
    """,
    re.VERBOSE,
)


def highlight(code: str) -> str:
    lines_out = []
    for line in code.split("\n"):
        parts = []
        prev_kw = None
        for m in _TOKEN_RE.finditer(line):
            kind = m.lastgroup
            text = m.group()
            cls = None
            if kind == "com":
                cls = "com"
            elif kind == "str":
                cls = "str"
            elif kind == "num":
                cls = "num"
            elif kind == "name":
                if prev_kw == "def":
                    cls = "fn"
                elif text in KEYWORDS:
                    cls = "kw"
                elif text in BUILTINS:
                    cls = "bi"
            # track whether the previous meaningful token was `def`
            if kind == "name":
                prev_kw = text if text in KEYWORDS else None
            elif kind == "ws":
                pass  # whitespace does not reset context
            else:
                prev_kw = None
            esc = html.escape(text)
            parts.append(f'<span class="{cls}">{esc}</span>' if cls else esc)
        lines_out.append("".join(parts))
    return "\n".join(lines_out)


# --------------------------------------------------------------------------- #
# Block constructors -> HTML
# --------------------------------------------------------------------------- #
def code(label, src, tone="navy", broken=False, validate=True):
    return {
        "type": "code", "label": label, "src": src.strip("\n"),
        "tone": tone, "broken": broken, "validate": validate,
    }


def para(text):
    return {"type": "para", "text": text}


def subhead(text):
    return {"type": "subhead", "text": text}


def bullets(items):
    return {"type": "bullets", "items": items}


def table(headers, rows):
    return {"type": "table", "headers": headers, "rows": rows}


def callout(label, text, tone="red"):
    return {"type": "callout", "label": label, "text": text, "tone": tone}


def code_font(n_lines):
    """Pick (font-pt, line-height) so a block of n_lines fits one page."""
    if n_lines <= 20:
        return (8.4, 1.42)
    if n_lines <= 30:
        return (7.5, 1.36)
    if n_lines <= 44:
        return (6.5, 1.30)
    if n_lines <= 60:
        return (6.0, 1.26)
    return (5.2, 1.22)


def render_block(b) -> str:
    t = b["type"]
    if t == "code":
        cls = "codepanel" + (" broken" if b["broken"] else "")
        src = b["src"]
        n = src.count("\n") + 1
        if n > 44:  # collapse blank runs on long dumps to reclaim height
            src = re.sub(r"\n{3,}", "\n\n", src)
            n = src.count("\n") + 1
        fs, lh = code_font(n)
        return (
            f'<div class="{cls}">'
            f'<div class="code-head tone-{b["tone"]}">{html.escape(b["label"])}</div>'
            f'<pre class="code" style="font-size:{fs}pt;line-height:{lh};">'
            f"<code>{highlight(src)}</code></pre>"
            f"</div>"
        )
    if t == "para":
        return f'<p class="body">{html.escape(b["text"])}</p>'
    if t == "subhead":
        return f'<h3 class="subhead">{html.escape(b["text"])}</h3>'
    if t == "bullets":
        lis = "".join(f"<li>{html.escape(i)}</li>" for i in b["items"])
        return f'<ul class="bullets">{lis}</ul>'
    if t == "table":
        head = "".join(f"<th>{html.escape(h)}</th>" for h in b["headers"])
        rows = ""
        for r in b["rows"]:
            cells = "".join(f"<td>{html.escape(c)}</td>" for c in r)
            rows += f"<tr>{cells}</tr>"
        return (
            f'<table class="grid"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
    if t == "callout":
        return (
            f'<div class="callout tone-{b["tone"]}">'
            f'<div class="callout-label">{html.escape(b["label"])}</div>'
            f'<div class="callout-body">{html.escape(b["text"])}</div>'
            f"</div>"
        )
    raise ValueError(t)


# --------------------------------------------------------------------------- #
# Canonical, corrected code snippets
# --------------------------------------------------------------------------- #
FILE_MAP = """
from easytello import tello

# Settings and feature switches

def pause(...):
    # shared helper

def turn(...):
    # shared helper

def maybe_flip(...):
    # optional feature

def fly_warmup(...):
    # required foundation

def fly_slalom(...):
    # mandatory routine

def fly_patrol(...):
    # optional routine

def fly_finale(...):
    # unlocks four minutes of flight time

def choose_routine():
    # user menu

def run_selected_routine(...):
    # conditional dispatch

def main():
    # connect, check, take off, run, land, close

if __name__ == "__main__":
    main()
"""

BROKEN_MOVE = """
def preview_move(distance):
print("Moving forward")
    print(f"Distance: {distance}")


preview_move(30)
"""

CORRECT_MOVE = """
def preview_move(distance):
    print("Moving forward")
    print(f"Distance: {distance}")


preview_move(30)
"""

PREVIEW_SQUARE = """
def preview_square(distance):
    for side in range(4):
        print(f"Side {side + 1}")
        print(f"Forward {distance}")
        print("Turn 90")
        print("---")


preview_square(30)
"""

PREVIEW_ZIGZAG = """
def preview_zigzag(steps, distance):
    for step in range(steps):
        print(f"Forward {distance}")

        if step % 2 == 0:
            print("Move left")
        else:
            print("Move right")


preview_zigzag(4, 30)
"""

SHARED_HELPERS = """
WAIT_TIME = 1
ENABLE_FLIPS = False


def pause(drone, seconds=WAIT_TIME):
    drone.wait(seconds)


def turn(drone, degrees, clockwise=True):
    if clockwise:
        drone.cw(degrees)
    else:
        drone.ccw(degrees)

    pause(drone)


def maybe_flip(drone, direction="f"):
    if ENABLE_FLIPS:
        drone.flip(direction)
        pause(drone, 2)
"""

FLY_WARMUP = """
def fly_warmup(
    drone,
    distance,
    height
):
    drone.up(height)
    pause(drone)

    drone.forward(distance)
    pause(drone)

    turn(drone, 90)

    drone.back(distance)
    pause(drone)

    drone.down(height)
    pause(drone)
"""

FLY_SLALOM = """
def fly_slalom(
    drone,
    steps,
    forward_distance,
    sideways_distance
):
    for step in range(steps):
        drone.forward(forward_distance)
        pause(drone)

        if step % 2 == 0:
            drone.left(sideways_distance)
        else:
            drone.right(sideways_distance)

        pause(drone)
"""

FLY_PATROL = """
def fly_patrol(
    drone,
    sides,
    distance,
    clockwise=True
):
    turn_angle = 360 // sides

    for side in range(sides):
        drone.forward(distance)
        pause(drone)
        turn(
            drone,
            turn_angle,
            clockwise
        )
"""

FLY_FINALE = """
def fly_finale(
    drone,
    distance,
    height,
    use_flip
):
    drone.up(height)
    pause(drone)

    for step in range(4):
        drone.forward(distance)
        turn(
            drone,
            90,
            clockwise=(step % 2 == 0)
        )

    if use_flip:
        maybe_flip(drone, "f")

    drone.down(height)
    pause(drone)
"""

SETTINGS_BLOCK = """
USE_MENU = True

ENABLE_WARMUP = True
ENABLE_SLALOM = True
ENABLE_PATROL = False
ENABLE_FINALE = False
ENABLE_FLIPS = False
"""

RUN_ENABLED = """
def run_enabled_routines(drone):
    if ENABLE_WARMUP:
        fly_warmup(drone, 30, 20)

    if ENABLE_SLALOM:
        fly_slalom(drone, 4, 30, 20)

    if ENABLE_PATROL:
        fly_patrol(drone, 5, 30)

    if ENABLE_FINALE:
        fly_finale(
            drone,
            25,
            20,
            use_flip=True
        )
"""

CHOOSE_ROUTINE = """
def choose_routine():
    print("1 - Warmup")
    print("2 - Slalom")
    print("3 - Patrol")
    print("4 - Finale")

    return input(
        "Choose a routine: "
    ).strip()


def run_selected_routine(
    drone,
    choice
):
    if choice == "1":
        fly_warmup(drone, 30, 20)

    elif choice == "2":
        fly_slalom(drone, 4, 30, 20)

    elif choice == "3":
        fly_patrol(drone, 5, 30)

    elif choice == "4":
        fly_finale(
            drone,
            25,
            20,
            use_flip=True
        )

    else:
        print("Unknown choice.")
        fly_warmup(drone, 20, 15)
"""

MAIN_FN = """
MIN_BATTERY = 40


def main():
    drone = tello.Tello()

    battery = int(
        drone.get_battery()
    )
    print(f"Battery: {battery}%")

    if battery < MIN_BATTERY:
        print(
            "Charge the drone "
            "before flying."
        )
        drone.close()
        return

    if USE_MENU:
        choice = choose_routine()

    drone.takeoff()
    pause(drone, 2)

    if USE_MENU:
        run_selected_routine(
            drone,
            choice
        )
    else:
        run_enabled_routines(drone)

    drone.land()
    drone.close()
"""

COMPLETE_1 = """
from easytello import tello

MIN_BATTERY = 40
WAIT_TIME = 1

USE_MENU = True

ENABLE_WARMUP = True
ENABLE_SLALOM = True
ENABLE_PATROL = False
ENABLE_FINALE = False
ENABLE_FLIPS = False


def pause(drone, seconds=WAIT_TIME):
    drone.wait(seconds)


def turn(drone, degrees, clockwise=True):
    if clockwise:
        drone.cw(degrees)
    else:
        drone.ccw(degrees)

    pause(drone)


def maybe_flip(drone, direction="f"):
    if ENABLE_FLIPS:
        drone.flip(direction)
        pause(drone, 2)


def fly_warmup(drone, distance, height):
    drone.up(height)
    pause(drone)

    drone.forward(distance)
    pause(drone)

    turn(drone, 90)

    drone.back(distance)
    pause(drone)

    drone.down(height)
    pause(drone)


def fly_slalom(
    drone,
    steps,
    forward_distance,
    sideways_distance
):
    for step in range(steps):
        drone.forward(forward_distance)
        pause(drone)

        if step % 2 == 0:
            drone.left(sideways_distance)
        else:
            drone.right(sideways_distance)

        pause(drone)
"""

COMPLETE_2 = """
def fly_patrol(
    drone,
    sides,
    distance,
    clockwise=True
):
    turn_angle = 360 // sides

    for side in range(sides):
        drone.forward(distance)
        pause(drone)
        turn(
            drone,
            turn_angle,
            clockwise
        )


def fly_finale(
    drone,
    distance,
    height,
    use_flip
):
    drone.up(height)
    pause(drone)

    for step in range(4):
        drone.forward(distance)
        turn(
            drone,
            90,
            clockwise=(step % 2 == 0)
        )

    if use_flip:
        maybe_flip(drone, "f")

    drone.down(height)
    pause(drone)


def choose_routine():
    print("1 - Warmup")
    print("2 - Slalom")
    print("3 - Patrol")
    print("4 - Finale")

    return input(
        "Choose a routine: "
    ).strip()


def run_selected_routine(drone, choice):
    if choice == "1":
        fly_warmup(drone, 30, 20)

    elif choice == "2":
        fly_slalom(drone, 4, 30, 20)

    elif choice == "3":
        fly_patrol(drone, 5, 30)

    elif choice == "4":
        fly_finale(
            drone,
            25,
            20,
            use_flip=True
        )

    else:
        print("Unknown choice.")
        fly_warmup(drone, 20, 15)
"""

COMPLETE_3 = """
def run_enabled_routines(drone):
    if ENABLE_WARMUP:
        fly_warmup(drone, 30, 20)

    if ENABLE_SLALOM:
        fly_slalom(drone, 4, 30, 20)

    if ENABLE_PATROL:
        fly_patrol(drone, 5, 30)

    if ENABLE_FINALE:
        fly_finale(
            drone,
            25,
            20,
            use_flip=True
        )


def main():
    drone = tello.Tello()

    battery = int(
        drone.get_battery()
    )
    print(f"Battery: {battery}%")

    if battery < MIN_BATTERY:
        print(
            "Charge the drone "
            "before flying."
        )
        drone.close()
        return

    if USE_MENU:
        choice = choose_routine()

    drone.takeoff()
    pause(drone, 2)

    if USE_MENU:
        run_selected_routine(
            drone,
            choice
        )
    else:
        run_enabled_routines(drone)

    drone.land()
    drone.close()


if __name__ == "__main__":
    main()
"""

STAGE_HEAD = ["Stage", "What to do", "Evidence"]

# --------------------------------------------------------------------------- #
# Page content
# --------------------------------------------------------------------------- #
PAGES = [
    dict(
        eyebrow="START SCREEN",
        title="Build one complete Python flight system",
        blocks=[
            para("You will develop one main.py file in stages. The first checkpoints "
                 "rebuild functions, indentation, loops, and conditionals. Later "
                 "checkpoints add reusable helpers, adjustable routines, feature "
                 "switches, a menu, flips, and geometry puzzles. Complete the required "
                 "checkpoints in order. Optional power-ups remain available after the "
                 "required program works."),
            table(STAGE_HEAD, [
                ["Checkpoint 1", "Repair a function and verify its indentation.", "Console preview"],
                ["Checkpoint 2", "Repeat movement with a for loop.", "Loop trace"],
                ["Checkpoint 3", "Choose movement with a conditional.", "Branch trace"],
                ["Checkpoint 4", "Create shared helper functions.", "DRY code"],
                ["Routine 2", "Complete the mandatory slalom routine.", "Working function"],
                ["Power-ups", "Add patrol, finale, menu, switches, and flips.", "Polished main.py"],
            ]),
            subhead("Required checkpoints"),
            para("Complete each code check before moving forward. When a result is "
                 "wrong, compare indentation, function calls, loop ranges, and branch "
                 "conditions one at a time."),
            subhead("Optional power-ups"),
            para("After the mandatory slalom works, add the patrol routine, the finale, "
                 "polygon calculations, and menu behavior. Each power-up should keep "
                 "the program readable."),
            callout("How to use this guide",
                    "Stop at every checkpoint. Type the code, predict the result, run a "
                    "console preview, and explain the control flow before requesting a "
                    "live flight check.", tone="blue"),
        ],
    ),
    dict(
        eyebrow="NORTH STAR",
        title="The finished file has one clear structure",
        blocks=[
            code("FILE MAP - MAIN.PY", FILE_MAP, tone="navy", validate=False),
            subhead("Why takeoff and landing belong in main()"),
            para("Each fly_* function should describe movement only. It should not "
                 "create another drone connection or repeat takeoff and landing. main() "
                 "performs those shared procedures once. This follows DRY: do not repeat "
                 "the same procedure in several places when one shared location can "
                 "control it."),
            subhead("Why helper functions appear first"),
            para("pause(), turn(), and maybe_flip() describe actions used by more than "
                 "one routine. The larger functions call these helpers rather than "
                 "rebuilding the same logic. Python must read a function definition "
                 "before it reaches a call to that function, so the file moves from "
                 "general tools toward complete missions."),
            callout("North-star rule",
                    "One connection, one takeoff, one landing, and several reusable "
                    "movement functions.", tone="blue"),
        ],
    ),
    dict(
        eyebrow="CHECKPOINT 01",
        title="Repair a function and its indentation",
        blocks=[
            code("BROKEN EXAMPLE - FIND TWO INDENTATION ERRORS", BROKEN_MOVE,
                 tone="red", broken=True, validate=False),
            subhead("What indentation means"),
            para("The colon after def preview_move(distance): begins a function body. "
                 "Every statement belonging to that function must move inward by the "
                 "same number of spaces. The function call belongs at file level, so it "
                 "returns to the left edge. Indentation is Python syntax: it determines "
                 "which statements belong together."),
            code("CORRECTED EXAMPLE - FUNCTION BODY AND FILE LEVEL", CORRECT_MOVE,
                 tone="teal"),
            subhead("Trace the call"),
            bullets([
                "Python stores the function definition.",
                "Python reaches preview_move(30).",
                "The argument 30 enters the parameter distance.",
                "Both indented print statements run.",
                "Execution returns to file level.",
            ]),
            callout("Checkpoint",
                    "Create preview_turn(angle) that prints the angle twice: once in a "
                    "sentence and once by itself.", tone="red"),
        ],
    ),
    dict(
        eyebrow="CHECKPOINT 02",
        title="Repeat a command pattern with a for loop",
        blocks=[
            code("CONSOLE PREVIEW - NO DRONE REQUIRED", PREVIEW_SQUARE, tone="teal"),
            subhead("Why the whole block repeats"),
            para("range(4) creates four cycles. During those cycles, side receives 0, "
                 "1, 2, and 3. Every statement indented beneath the for line belongs to "
                 "the loop and repeats. The blank line after the block returns execution "
                 "to the function's outer indentation level."),
            table(STAGE_HEAD, [
                ["Cycle 1", "side = 0", "Prints Side 1"],
                ["Cycle 2", "side = 1", "Prints Side 2"],
                ["Cycle 3", "side = 2", "Prints Side 3"],
                ["Cycle 4", "side = 3", "Prints Side 4"],
            ]),
            subhead("Logic puzzle"),
            para("A regular polygon completes one full rotation across all of its "
                 "corners. Divide 360 by the number of sides to calculate each exterior "
                 "turn. A hexagon needs 60-degree turns. An octagon needs 45-degree "
                 "turns. Calculate the turn for a nine-sided route before checking with "
                 "Python."),
            callout("Checkpoint",
                    "Create preview_polygon(sides, distance). Calculate "
                    "turn_angle = 360 // sides, then preview every side and turn.",
                    tone="red"),
        ],
    ),
    dict(
        eyebrow="CHECKPOINT 03",
        title="Choose a direction with a conditional",
        blocks=[
            code("LOOP + IF/ELSE", PREVIEW_ZIGZAG, tone="blue"),
            subhead("What step % 2 tests"),
            para("The modulo operator returns a remainder. Even values divide by two "
                 "with remainder zero, so step % 2 == 0 is True for 0, 2, 4, and so on. "
                 "Odd values reach the else branch. The loop controls how many steps "
                 "occur; the conditional controls which sideways movement belongs to "
                 "each step."),
            table(STAGE_HEAD, [
                ["step = 0", "Even branch", "Left"],
                ["step = 1", "Odd branch", "Right"],
                ["step = 2", "Even branch", "Left"],
                ["step = 3", "Odd branch", "Right"],
            ]),
            subhead("Logic puzzle"),
            para("Predict the branch sequence for seven steps. Then change the "
                 "comparison to step % 3 == 0. Which step values reach the first branch? "
                 "Write the sequence before running the program."),
            callout("Checkpoint",
                    "Create choose_turn(step) that returns 'left' for even steps and "
                    "'right' for odd steps.", tone="red"),
        ],
    ),
    dict(
        eyebrow="CHECKPOINT 04",
        title="Create shared helpers and keep the file DRY",
        blocks=[
            code("SHARED HELPERS - DEFINED ONCE", SHARED_HELPERS, tone="purple"),
            subhead("Default parameter values"),
            para("seconds=WAIT_TIME and clockwise=True provide default values. "
                 "pause(drone) uses the shared wait time, while pause(drone, 2) "
                 "overrides it. turn(drone, 90) rotates clockwise by default. "
                 "turn(drone, 90, False) selects the counterclockwise branch."),
            subhead("Feature switches"),
            para("ENABLE_FLIPS is a Boolean setting stored near the top of the file. "
                 "When it is False, maybe_flip() performs no flip. When it is True, the "
                 "same function allows the command. This keeps optional behavior in one "
                 "location instead of scattering extra if statements throughout every "
                 "routine."),
            callout("DRY check",
                    "Search the file for drone.cw and drone.ccw. After adding turn(), "
                    "those method calls should remain inside the helper rather than "
                    "being repeated everywhere.", tone="red"),
        ],
    ),
    dict(
        eyebrow="ROUTINE 01",
        title="Build fly_warmup()",
        blocks=[
            code("REQUIRED FOUNDATION ROUTINE", FLY_WARMUP, tone="navy"),
            subhead("Follow the parameters"),
            para("distance controls the forward and backward travel. height controls "
                 "the vertical travel. The same values can be changed at the function "
                 "call without rewriting the routine. The drone should finish near its "
                 "starting height and front-to-back position, but it should face a new "
                 "direction because of the ninety-degree turn."),
            table(STAGE_HEAD, [
                ["Preview", "Replace EasyTello methods with print statements.", "Expected sequence"],
                ["Trace", "Record height, position, and heading after every command.", "Five-row trace"],
                ["Code", "Type the function with consistent indentation.", "No syntax errors"],
                ["Explain", "State what each parameter controls.", "Two sentences"],
            ]),
            callout("Required check",
                    "The routine contains movement only. takeoff(), land(), and close() "
                    "belong in main().", tone="red"),
        ],
    ),
    dict(
        eyebrow="ROUTINE 02 - MANDATORY",
        title="Build fly_slalom()",
        blocks=[
            code("MANDATORY ROUTINE - LOOP + CONDITIONAL + PARAMETERS", FLY_SLALOM,
                 tone="purple"),
            subhead("Why this routine matters"),
            para("fly_slalom() combines the foundation skills in one routine. The "
                 "function packages a complete behavior. Parameters adjust the route. "
                 "The loop repeats each slalom step. The conditional alternates left and "
                 "right movement. The function remains reusable because no distance or "
                 "repetition count is locked into its body."),
            table(STAGE_HEAD, [
                ["1", "Preview fly_slalom(None, 4, 30, 20) using print statements.", "Eight actions"],
                ["2", "Write the EasyTello version.", "Correct indentation"],
                ["3", "Change steps from 4 to 5 and predict the final sideways direction.", "Written prediction"],
                ["4", "Explain why the conditional belongs inside the loop.", "One paragraph"],
            ]),
            callout("Mandatory completion",
                    "Do not begin Routine 3 until fly_slalom() previews correctly and "
                    "the branch sequence is left, right, left, right.", tone="red"),
        ],
    ),
    dict(
        eyebrow="ROUTINE 03 - OPTIONAL",
        title="Build fly_patrol()",
        blocks=[
            code("OPTIONAL POLYGON ROUTINE", FLY_PATROL, tone="teal"),
            subhead("The route calculates its own turn"),
            para("The function receives the number of sides and calculates the exterior "
                 "angle. Calling fly_patrol(drone, 5, 30) creates a five-sided plan with "
                 "72-degree turns. Calling fly_patrol(drone, 8, 30, False) creates an "
                 "eight-sided plan with 45-degree counterclockwise turns."),
            subhead("Think before running"),
            bullets([
                "Which argument creates a triangle?",
                "Which argument creates a hexagon?",
                "What turn angle results from twelve sides?",
                "What changes when clockwise becomes False?",
                "Which values could create a route too large for the available area?",
            ]),
            callout("Optional power-up",
                    "Add a label parameter and print the route name, side count, "
                    "distance, and turn angle before movement begins.", tone="teal"),
        ],
    ),
    dict(
        eyebrow="ROUTINE 04 - FLIGHT TIME UNLOCK",
        title="Build fly_finale()",
        blocks=[
            code("FINALE ROUTINE - FOUR-MINUTE FLIGHT CHECK", FLY_FINALE, tone="red"),
            subhead("A Boolean argument controls the optional feature"),
            para("use_flip belongs to this function call. ENABLE_FLIPS belongs to the "
                 "program settings. Both must permit the flip before it occurs: the "
                 "routine must request it, and the global feature switch must allow it. "
                 "This creates two separate controls for a movement that should never "
                 "occur accidentally."),
            subhead("Explain the alternating turns"),
            para("clockwise=(step % 2 == 0) passes a Boolean expression directly into "
                 "turn(). Even steps rotate clockwise; odd steps rotate "
                 "counterclockwise. Trace all four values of step and write the heading "
                 "changes before requesting a flight check."),
            callout("Unlock requirement",
                    "A correct console preview, a complete trace, and a clear "
                    "explanation of both flip controls unlock four minutes of live "
                    "flight time.", tone="red"),
        ],
    ),
    dict(
        eyebrow="FEATURE SWITCHES",
        title="Turn program sections on and off",
        blocks=[
            code("FILE LEVEL - PROGRAM SETTINGS", SETTINGS_BLOCK, tone="navy"),
            subhead("Settings change behavior without changing routines"),
            para("These Boolean values act as switches. The routine definitions remain "
                 "untouched. Changing ENABLE_PATROL from False to True allows the "
                 "program to call fly_patrol(). Changing it back disables that section "
                 "again. A feature switch is useful when one polished file contains both "
                 "required and optional behavior."),
            code("FUNCTION - RUN EVERY ENABLED ROUTINE", RUN_ENABLED, tone="blue"),
            callout("Modular test",
                    "Enable one routine at a time during development. Several "
                    "individually correct routines can still create an unsafe combined "
                    "route.", tone="red"),
        ],
    ),
    dict(
        eyebrow="USER MENU",
        title="Select one routine at runtime",
        blocks=[
            code("MENU INPUT -> CONDITIONAL DISPATCH", CHOOSE_ROUTINE, tone="blue"),
            subhead("Why the menu returns text"),
            para("input() returns a string, so the comparisons use '1', '2', '3', and "
                 "'4'. run_selected_routine() maps each choice to one function call. The "
                 "final else branch provides a predictable fallback instead of allowing "
                 "an unknown input to reach no routine at all."),
            callout("Menu puzzle",
                    "Add choice 5 for a seven-sided patrol. Calculate the required turn "
                    "before writing the function call.", tone="red"),
        ],
    ),
    dict(
        eyebrow="ASSEMBLY",
        title="main() controls the complete program",
        blocks=[
            code("FUNCTION - ONE CONNECTION, ONE TAKEOFF, ONE LANDING", MAIN_FN,
                 tone="navy"),
            subhead("Follow the decision order"),
            para("main() creates the EasyTello connection and requests the battery "
                 "value. A low value closes the connection and returns before takeoff. "
                 "When the check passes, USE_MENU chooses between one menu-selected "
                 "routine and the set of enabled routines. Both paths share the same "
                 "takeoff, landing, and close procedures."),
            callout("Assembly check",
                    "Search main.py for takeoff(), land(), and close(). Each should "
                    "appear once in the final architecture.", tone="red"),
        ],
    ),
    dict(
        eyebrow="COMPLETE MAIN.PY - PART 1",
        title="Settings, helpers, and required routines",
        blocks=[
            code("FILE LEVEL -> END OF fly_slalom()", COMPLETE_1, tone="navy"),
            para("This section defines configuration values, shared helpers, the "
                 "foundation routine, and the mandatory slalom. Every function shown "
                 "here is complete before the next section begins."),
        ],
    ),
    dict(
        eyebrow="COMPLETE MAIN.PY - PART 2",
        title="Optional routines and menu selection",
        blocks=[
            code("FUNCTION SCOPE - fly_patrol() -> END OF run_selected_routine()",
                 COMPLETE_2, tone="purple"),
            para("This section adds the polygon and finale routines, then maps menu "
                 "choices to named function calls. The page begins and ends at function "
                 "boundaries."),
        ],
    ),
    dict(
        eyebrow="COMPLETE MAIN.PY - PART 3",
        title="Feature switches, main(), and the entry point",
        blocks=[
            code("FUNCTION SCOPE - run_enabled_routines() -> FILE LEVEL", COMPLETE_3,
                 tone="navy"),
            para("The final section chooses enabled routines or a menu-selected "
                 "routine. main() owns the shared connection, battery check, takeoff, "
                 "landing, and close procedures."),
        ],
    ),
    dict(
        eyebrow="FINAL CHECK",
        title="Prove the program before flight",
        blocks=[
            table(STAGE_HEAD, [
                ["Syntax", "Run the file far enough to confirm that Python accepts every definition.", "No SyntaxError"],
                ["Structure", "Locate every def line and identify where its indentation ends.", "Function map"],
                ["Loop", "Trace all values used by fly_slalom() and fly_finale().", "Cycle table"],
                ["Branches", "Predict every left/right and clockwise/counterclockwise decision.", "Branch sequence"],
                ["DRY", "Confirm takeoff(), land(), and close() appear in main() only.", "Three searches"],
                ["Preview", "Describe the selected route from beginning to end.", "Spoken explanation"],
            ]),
            subhead("Common debugging questions"),
            bullets([
                "Is the function defined before it is called?",
                "Does every indented block use a consistent number of spaces?",
                "Does the function call supply the expected number of arguments?",
                "Does the loop repeat the intended number of times?",
                "Does each conditional compare values of compatible types?",
                "Is the computer connected to the Tello Wi-Fi network?",
                "Does each fly_* routine contain movement only?",
            ]),
            subhead("Four-minute unlock"),
            para("To unlock the finale flight check, present a correct console preview, "
                 "trace the four loop cycles, explain the two flip controls, and show "
                 "that the program contains one shared takeoff and one shared landing."),
            callout("Final logic puzzle",
                    "Create a menu choice for a regular ten-sided patrol. Determine the "
                    "turn angle, write the function call, and predict the final "
                    "heading.", tone="red"),
        ],
    ),
]


# --------------------------------------------------------------------------- #
# Validation: every real code block must compile
# --------------------------------------------------------------------------- #
def validate_code():
    errors = []
    for i, page in enumerate(PAGES):
        for b in page["blocks"]:
            if b.get("type") == "code" and b.get("validate"):
                try:
                    compile(b["src"], f"<page{i + 2}:{b['label']}>", "exec")
                except SyntaxError as e:
                    errors.append(f"page {i + 2} [{b['label']}]: {e}")
    if errors:
        print("CODE VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("Code validation passed: all flagged blocks compile.")


# --------------------------------------------------------------------------- #
# HTML assembly
# --------------------------------------------------------------------------- #
def topbar(n):
    return (
        '<div class="topbar">'
        '<span class="tb-left">DRONE CAMP <span class="dot">/</span> DAY 4</span>'
        f'<span class="tb-right">PAGE {n}</span>'
        "</div>"
    )


def footer():
    return (
        '<div class="pagefoot">'
        f'<div class="tagline">{html.escape(TAGLINE)}</div>'
        f'<div class="chain">{CHAIN}</div>'
        "</div>"
    )


def cover():
    return f"""
<section class="page cover">
  <div class="cover-frame">
    <div class="cover-header">
      <div class="ch-title">DRONE CAMP</div>
      <div class="ch-sub">FUNCTIONS / LOOPS / MENUS / FEATURE SWITCHES</div>
      <div class="ch-badge">DAY 4</div>
    </div>
    <div class="cover-body">
      <div class="emblem">
        <div class="emblem-ring"><span>D4</span></div>
        <div class="emblem-cap">DRONE CAMP</div>
      </div>
      <div class="cover-card">
        <div class="cc-kicker">ONE POLISHED FLIGHT SYSTEM</div>
        <div class="cc-dots"></div>
        <div class="pyramid"><span class="py-label">FLIGHT<br>SYSTEM</span></div>
        <div class="cc-python">PYTHON</div>
        <div class="cc-file">MAIN.PY</div>
      </div>
    </div>
    <div class="cover-foot">
      <span>READ / TRACE / CODE / PREVIEW / FLY</span>
      <span>DRONE CAMP</span>
    </div>
  </div>
</section>
"""


def render_page(n, page):
    blocks = "".join(render_block(b) for b in page["blocks"])
    return f"""
<section class="page">
  {topbar(n)}
  <div class="content">
    <div class="eyebrow">{html.escape(page['eyebrow'])}</div>
    <h1 class="title">{html.escape(page['title'])}</h1>
    {blocks}
  </div>
  {footer()}
</section>
"""


CSS = """
:root{
  --ink:#0b1224; --cream:#fbf1d3; --paper:#fdf6e3;
  --red:#e12a24; --blue:#1a49c9; --yellow:#ffcf24; --teal:#0e968c;
  --purple:#a51f6e; --navy:#14224e;
  --line:#e4dcc0; --muted:#5c5540;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background:#31353d;}
body{font-family:'Open Sans',"Helvetica Neue",Arial,sans-serif;color:var(--ink);
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}
.page{position:relative;width:8.5in;height:11in;background:var(--paper);
  overflow:hidden;page-break-after:always;margin:0 auto;}
.page:last-child{page-break-after:auto;}

/* condensed display treatment for headings via Open Sans width axis */
.title,.eyebrow,.tb-left,.tb-right,.code-head,.grid th,.callout-label,
.ch-title,.ch-badge,.cc-python,.cc-file,.subhead{
  font-family:'Open Sans',"Helvetica Neue",Arial,sans-serif;
  font-stretch:75%;
}

/* ---- top bar ---- */
.topbar{height:0.62in;background:var(--blue);color:#fff;display:flex;
  align-items:center;justify-content:space-between;padding:0 0.55in;
  font-weight:700;letter-spacing:.06em;}
.topbar .tb-left{font-size:12.5pt;}
.topbar .tb-right{font-size:11pt;opacity:.9;}
.topbar .dot{color:var(--yellow);margin:0 .25em;}

/* ---- content ---- */
.content{padding:0.3in 0.55in 0.72in;}
.eyebrow{color:var(--red);font-weight:700;letter-spacing:.18em;
  font-size:9.5pt;margin:.04in 0 .03in;}
.title{font-size:25pt;font-weight:700;letter-spacing:.005em;margin:0 0 .11in;
  color:var(--ink);line-height:1.02;}
.subhead{font-size:13pt;font-weight:700;margin:.12in 0 .04in;color:var(--ink);
  letter-spacing:.01em;}
p.body{font-size:9.7pt;line-height:1.5;margin:.04in 0 .07in;color:#26210f;}

/* ---- code panels ---- */
.codepanel{border-radius:7px;overflow:hidden;margin:.05in 0 .12in;
  box-shadow:0 1px 0 rgba(0,0,0,.08);border:1px solid #101a36;}
.code-head{color:#fff;font-weight:700;letter-spacing:.12em;font-size:9pt;
  padding:7px 12px;}
.tone-navy{background:var(--navy);}
.tone-red{background:var(--red);}
.tone-teal{background:var(--teal);}
.tone-blue{background:var(--blue);}
.tone-purple{background:var(--purple);}
pre.code{margin:0;background:#0f1830;color:#e6ecff;padding:11px 14px;
  font-family:"SF Mono","DejaVu Sans Mono",Menlo,Consolas,monospace;
  font-size:8.4pt;line-height:1.42;white-space:pre;overflow:hidden;}
.codepanel.broken pre.code{background:#241016;}
.code .kw{color:#ff9270;}
.code .str{color:#8ce39a;}
.code .com{color:#8091b4;font-style:italic;}
.code .num{color:#ffd15c;}
.code .fn{color:#6fb4ff;font-weight:600;}
.code .bi{color:#c79bff;}

/* ---- bullets ---- */
ul.bullets{margin:.03in 0 .09in;padding-left:.28in;}
ul.bullets li{font-size:9.7pt;line-height:1.42;margin:.015in 0;color:#26210f;}

/* ---- tables ---- */
table.grid{width:100%;border-collapse:collapse;margin:.06in 0 .12in;
  font-size:9pt;}
table.grid th{background:var(--blue);color:#fff;text-align:left;
  padding:6px 10px;font-weight:700;letter-spacing:.04em;font-size:9pt;}
table.grid td{padding:5px 10px;border-bottom:1px solid var(--line);color:#26210f;
  vertical-align:top;}
table.grid tbody tr:nth-child(odd){background:#f6ecca;}

/* ---- callouts ---- */
.callout{display:flex;margin:.1in 0 .05in;border-radius:6px;overflow:hidden;
  border:1px solid var(--line);}
.callout-label{flex:0 0 1.55in;color:#fff;font-weight:700;padding:9px 12px;
  font-size:9.5pt;letter-spacing:.03em;display:flex;align-items:center;}
.callout-body{flex:1;background:#f6ecca;padding:9px 12px;font-size:9.3pt;
  line-height:1.4;color:#26210f;}
.callout.tone-red .callout-label{background:var(--red);}
.callout.tone-blue .callout-label{background:var(--blue);}
.callout.tone-teal .callout-label{background:var(--teal);}

/* ---- footer ---- */
.pagefoot{position:absolute;left:0;right:0;bottom:0;padding:0 0.55in .16in;}
.pagefoot .tagline{border-top:1.5px solid var(--ink);padding-top:6px;
  text-align:center;font-size:8.5pt;color:var(--muted);}
.pagefoot .chain{margin-top:3px;font-size:7.5pt;letter-spacing:.14em;
  color:var(--blue);font-weight:700;}

/* ---- cover ---- */
.cover{background:#000;}
.cover-frame{position:absolute;inset:0.34in;background:var(--cream);
  border-radius:16px;padding:0.3in;display:flex;flex-direction:column;
  border:2px solid #0a0a0a;}
.cover-header{position:relative;background:var(--red);border:5px solid var(--blue);
  border-radius:14px;padding:18px 22px;}
.ch-title{color:var(--yellow);font-size:44pt;font-weight:800;letter-spacing:.01em;
  line-height:.95;}
.ch-sub{color:#ffe6a8;font-size:8.5pt;letter-spacing:.12em;margin-top:2px;}
.ch-badge{position:absolute;right:22px;top:50%;transform:translateY(-50%);
  background:var(--blue);color:var(--yellow);border:3px solid var(--yellow);
  border-radius:8px;padding:10px 20px;font-size:20pt;font-weight:800;}
.cover-body{flex:1;position:relative;display:flex;align-items:center;
  justify-content:flex-end;padding:0.2in 0;}
.emblem{position:absolute;left:0.1in;bottom:0.7in;text-align:center;}
.emblem-ring{width:2.1in;height:2.1in;border-radius:50%;background:var(--blue);
  border:8px solid var(--yellow);display:flex;align-items:center;
  justify-content:center;
  background-image:repeating-linear-gradient(0deg,transparent 0 14px,rgba(225,42,36,.55) 14px 15px),
                   repeating-linear-gradient(90deg,transparent 0 14px,rgba(225,42,36,.55) 14px 15px);}
.emblem-ring span{color:#fff;font-size:34pt;font-weight:800;
  font-family:"Arial Narrow",Arial,sans-serif;text-shadow:0 2px 6px rgba(0,0,0,.4);}
.emblem-cap{margin-top:6px;color:var(--blue);font-weight:800;font-size:9pt;
  letter-spacing:.12em;}
.cover-card{position:relative;width:4.3in;height:5in;background:var(--red);
  border-radius:16px;padding:20px;color:#fff;overflow:hidden;
  box-shadow:0 8px 22px rgba(0,0,0,.35);}
.cc-kicker{color:var(--yellow);font-weight:700;font-size:9pt;letter-spacing:.08em;}
.cc-dots{position:absolute;left:22px;top:70px;width:1.5in;height:2.3in;
  background-image:radial-gradient(var(--yellow) 1.4px,transparent 1.6px);
  background-size:15px 15px;opacity:.9;}
.pyramid{position:absolute;right:12px;top:74px;width:0;height:0;
  border-left:1.45in solid transparent;border-right:1.45in solid transparent;
  border-bottom:2.5in solid var(--blue);
  filter:drop-shadow(0 0 0 var(--yellow));}
.pyramid:before{content:"";position:absolute;left:-1.45in;top:0;width:0;height:0;
  border-left:1.45in solid transparent;border-right:1.45in solid transparent;
  border-bottom:2.5in solid transparent;
  background:repeating-linear-gradient(0deg,transparent 0 15px,rgba(255,207,36,.5) 15px 16px);}
.py-label{position:absolute;left:-0.55in;top:1.35in;color:var(--yellow);
  font-size:7.5pt;font-weight:700;letter-spacing:.1em;text-align:center;
  line-height:1.15;}
.cc-python{position:absolute;right:26px;bottom:1.1in;color:var(--yellow);
  font-size:26pt;font-weight:800;}
.cc-file{position:absolute;left:22px;bottom:22px;color:var(--yellow);
  font-size:32pt;font-weight:800;letter-spacing:.02em;}
.cover-foot{display:flex;justify-content:space-between;border-top:2px solid var(--ink);
  padding-top:10px;color:var(--blue);font-weight:700;font-size:8.5pt;
  letter-spacing:.1em;}
"""


def build_html():
    pages_html = [cover()]
    for i, page in enumerate(PAGES):
        pages_html.append(render_page(i + 2, page))
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Drone Camp - Day 4 - Flight System</title>
<style>@page{{size:Letter;margin:0;}}
{font_face_css()}
{CSS}</style></head>
<body>
{''.join(pages_html)}
</body></html>
"""
    HTML_OUT.write_text(doc, encoding="utf-8")
    print(f"Wrote HTML -> {HTML_OUT.name}")


def find_chrome():
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def build_pdf():
    chrome = find_chrome()
    if not chrome:
        print("Chrome not found; wrote HTML only.")
        return
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT}",
        HTML_OUT.as_uri(),
    ]
    print("Rendering PDF via Chrome...")
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Wrote PDF -> {PDF_OUT.name}")


if __name__ == "__main__":
    validate_code()
    build_html()
    if "--html" not in sys.argv:
        build_pdf()
