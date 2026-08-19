# PaceChart

A desktop tool for Green Hope XC: scrapes the team's roster and meet results, lets a coach pick which results to use per athlete, converts everything to a 5k-equivalent time, and generates a training-pace PDF (one sheet per gender).

See [Design.md](Design.md) for the full design/workflow spec and [Calculator-Methodology.md](Calculator-Methodology.md) for the math behind the pace calculations.

## Requirements

- Windows (the app looks for the Georgia font and `%APPDATA%` in Windows-specific locations, with graceful fallbacks elsewhere)
- Python 3.11+

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Running the app

```powershell
.venv\Scripts\pacechart.exe
```

(or `.venv\Scripts\python.exe -m pacechart.gui`)

This opens the GUI, which follows the workflow in [Design.md](Design.md):

1. **Load Data** — scrapes the roster and schedule, then every posted meet result.
2. On the **Boys** / **Girls** tabs, check which result(s) each athlete should use (or click **Select Most Recent** to auto-select each athlete's latest result).
3. On the **Paces** tab, enable the zone x distance combinations you want in the output. Click a row or column header to toggle everything in it at once, or save/load a named selection as a template.
4. Click **Calc** to average each athlete's selected results into a 5k-equivalent time and generate every enabled pace. Use **Group by** to order the output by zone or by distance.
5. Click **Generate PDF** to export — it auto-switches to landscape, and splits into multiple tables per page if a selection is too wide even for that.

## Running tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Tests run in CI on every pull request and push to `master` (see `.github/workflows/tests.yml`).

## Building the installer

Coaches don't need Python installed — the app ships as a per-user Windows
installer that requires no admin rights (installs to
`%LocalAppData%\Programs\PaceChart`.

A fresh installer is built automatically on every push to `master` (see
`.github/workflows/build-installer.yml`) and uploaded as a workflow artifact.
To build one locally:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[build]"
.venv\Scripts\python.exe -m PyInstaller packaging\pacechart.spec --distpath build\dist --workpath build\work --noconfirm
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DMyAppVersion=0.1.0" packaging\installer.iss
```

This needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed
(`winget install JRSoftware.InnoSetup` or `choco install innosetup`). The
resulting `PaceChartSetup.exe` is written to `build\installer\`.

## Project layout

```
src/pacechart/
  calculator.py   # the pace/equivalent-performance model (see Calculator-Methodology.md)
  models.py       # Athlete, RaceResult, Meet, and the 5k-equivalent averaging logic
  scraper.py      # roster/schedule/results page parsing + fetching
  app_state.py    # GUI-independent application state (selections, calculation, templates)
  templates.py    # persisted pace-selection templates (%APPDATA%\PaceChart\templates.json)
  pdf.py          # PDF report generation
  gui.py          # the Tkinter application
tests/            # pytest suite, with saved HTML fixtures for the scraper tests
```

## License

[MIT](LICENSE)
