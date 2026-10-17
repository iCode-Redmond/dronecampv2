Drone camp starter files

## Windows setup

Open **PowerShell**, `cd` into this project folder, then paste the block below.
The first line allows the virtual environment's activate script to run for this
session (Windows blocks it by default).

```powershell
# Allow venv activation for this PowerShell session only
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

# Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

You're ready to go. Run a day's script with, for example:

```powershell
python day1\main.py
```

## Practice Python in the browser

169 problems, nothing to install:
**https://icode-redmond.github.io/python-problem-bank/**
(source: [python-problem-bank](https://github.com/iCode-Redmond/python-problem-bank))

## Drone Dispatch — the challenge game

Write Python, watch a drone fly it. Twenty-eight levels across fifteen chapters.

- **Core course (chapters 1–7):** variables, if/else, lists, for loops,
  functions, dictionaries, and a mission that needs all six.
- **Advanced track (chapters 8–15):** while loops, elif and `and`/`or`,
  return values, nested loops, `try`/`except`, classes, comprehensions and
  sorting, and a grand finale that combines them.

Some advanced levels fly your code more than once with different data (the
`cases` field on a level), so a solution has to handle every input rather
than one hard-coded answer. A few starters crash on purpose
(`starterRaises`), because seeing the error is the lesson.
**https://icode-redmond.github.io/dronecampv2/challenge/**

The commands are the real EasyTello API — `takeoff`, `land`, `forward`, `cw`,
`ccw`, `flip`, `speed`, `get_battery` — so the same lines fly a real Tello.
`deliver()` is the one invention; a Tello carries nothing.

Everything lives in `challenge/index.html`. To work on it:

```bash
python3 -m http.server 8123          # then open /challenge/

node challenge/test/logic.test.js    # levels, maps, solutions, fuzz (no browser)

# browser suite — needs Chrome on :9222 first
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/dd about:blank &
node challenge/test/browser.test.js http://localhost:8123/challenge/
```

Run both before pushing. The browser suite is the one that catches what static
checks cannot — a crashed flight that leaves the Run button stuck, for instance.

Final:
[GOOD LUCK CAMPERS!](https://icode-redmond.github.io/dronecampv2/)
