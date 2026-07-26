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
