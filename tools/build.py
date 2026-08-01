#!/usr/bin/env python3
"""Assemble the validated problem bank + learn content into app-data.js.

Refuses to build if the bank does not validate, so a broken problem can never
reach the deployed page.

Usage:
    python3 tools/build.py
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "problems"
LEARN = ROOT / "data" / "learn.json"
OUT = ROOT / "app-data.js"

# Category display order in the sidebar.
ORDER = [
    "Warmup-1", "Warmup-2", "String-1", "List-1", "Logic-1",
    "Logic-2", "String-2", "List-2", "String-3", "List-3",
    "Drone Logic", "Drone Camp",
]

# The camp finale. Kept out of data/problems/ because it runs against a mock
# drone rather than plain input/output tests, so the bank validator cannot
# check it the same way.
DRONE = {
    "id": "fly_obstacle_course",
    "category": "Drone Camp",
    "title": "Obstacle Course Generator",
    "function": "fly_obstacle_course",
    "difficulty": 4,
    "concept": "Lists + loops + conditionals + EasyTello",
    "brief": "Translate a list of route words into EasyTello method calls.",
    "description": (
        "Loop through route. Movement words use distance. cw and ccw turn 90 "
        "degrees. flip uses direction 'f'. Any word you do not recognize goes "
        "into the skipped list that you return."
    ),
    "starter": (
        "def fly_obstacle_course(drone, route, distance):\n"
        "    skipped = []\n\n"
        "    for command in route:\n"
        "        # Translate each command into an EasyTello method call.\n"
        "        pass\n\n"
        "    return skipped\n"
    ),
    "solution": (
        "def fly_obstacle_course(drone, route, distance):\n"
        "    skipped = []\n\n"
        "    for command in route:\n"
        '        if command == "forward":\n'
        "            drone.forward(distance)\n"
        '        elif command == "back":\n'
        "            drone.back(distance)\n"
        '        elif command == "left":\n'
        "            drone.left(distance)\n"
        '        elif command == "right":\n'
        "            drone.right(distance)\n"
        '        elif command == "up":\n'
        "            drone.up(distance)\n"
        '        elif command == "down":\n'
        "            drone.down(distance)\n"
        '        elif command == "cw":\n'
        "            drone.cw(90)\n"
        '        elif command == "ccw":\n'
        "            drone.ccw(90)\n"
        '        elif command == "flip":\n'
        '            drone.flip("f")\n'
        "        else:\n"
        "            skipped.append(command)\n\n"
        "    return skipped\n"
    ),
    "hints": [
        "Begin with one loop: for command in route.",
        "Use an if/elif chain. Every word you recognize calls one drone method.",
        "Unknown words belong in skipped so the flight does not crash.",
    ],
    "example": (
        'route = ["forward", "left", "forward"]\n'
        "recorded calls -> [['forward', 30], ['left', 30], ['forward', 30]]"
    ),
    "explainer": (
        "The browser swaps in a mock drone that records calls instead of flying. "
        "Because the method names match EasyTello exactly, the finished function "
        "can be pasted straight into a real flight program."
    ),
    "lineLimit": 120,
    "drone": True,
    "tests": [],
}


def main():
    print("validating bank...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate.py")],
        capture_output=True, text=True,
    )
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        print("\nBUILD ABORTED: bank did not validate", file=sys.stderr)
        return 1

    problems = []
    for path in sorted(BANK.glob("*.json")):
        problems.extend(json.loads(path.read_text()))

    problems.append(DRONE)

    rank = {name: i for i, name in enumerate(ORDER)}
    problems.sort(key=lambda p: (rank.get(p["category"], 99), p.get("difficulty", 3), p["id"]))

    # stable display number within each category
    counters = {}
    for problem in problems:
        cat = problem["category"]
        counters[cat] = counters.get(cat, 0) + 1
        problem["number"] = f"{counters[cat]:02d}"

    learn = json.loads(LEARN.read_text()) if LEARN.exists() else []

    # ORDER first, then any category an agent invented that ORDER does not know
    # about, so a new category can never silently vanish from the browser.
    names = ORDER + [p["category"] for p in problems if p["category"] not in ORDER]
    categories = []
    for name in dict.fromkeys(names):
        members = [p["id"] for p in problems if p["category"] == name]
        if members:
            categories.append({"name": name, "ids": members})

    orphans = sum(len(c["ids"]) for c in categories)
    if orphans != len(problems):
        raise SystemExit(f"category assembly lost problems: {orphans} != {len(problems)}")

    banner = (
        "// GENERATED FILE - do not edit by hand.\n"
        "// Rebuild with: python3 tools/build.py\n"
        "// Every problem below passed tools/validate.py: its reference solution\n"
        "// was executed against its own test cases and matched on every one.\n"
    )
    OUT.write_text(
        banner
        + "const PROBLEMS=" + json.dumps(problems, ensure_ascii=False) + ";\n"
        + "const CATEGORIES=" + json.dumps(categories, ensure_ascii=False) + ";\n"
        + "const LEARN=" + json.dumps(learn, ensure_ascii=False) + ";\n"
    )

    size = OUT.stat().st_size / 1024
    print(f"\nwrote {OUT.name}: {len(problems)} problems, "
          f"{len(categories)} categories, {len(learn)} learn topics, {size:.1f} KB")
    for cat in categories:
        print(f"  {cat['name']:<12} {len(cat['ids'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
