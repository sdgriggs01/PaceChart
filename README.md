# PaceChart

[![Tests](https://github.com/sdgriggs01/PaceChart/actions/workflows/tests.yml/badge.svg)](https://github.com/sdgriggs01/PaceChart/actions/workflows/tests.yml)
[![Build installer](https://github.com/sdgriggs01/PaceChart/actions/workflows/build-installer.yml/badge.svg)](https://github.com/sdgriggs01/PaceChart/actions/workflows/build-installer.yml)

A desktop tool for Ggenerating pace charts driven by recent meet results.

**[⬇ Download the latest installer](https://github.com/sdgriggs01/PaceChart/releases/latest)**. See [Building the installer](#building-the-installer) below for how it's built.

See [Design.md](Design.md) for the full design/workflow spec and [Calculator-Methodology.md](Calculator-Methodology.md) for the math behind the pace calculations.

## Requirements

- Windows, macOS, or a Chromebook with Linux (Crostini) enabled (the app looks for the Georgia font and `%APPDATA%` in Windows-specific locations, with graceful fallbacks elsewhere)
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

## Installing (coaches)

Coaches don't need Python installed. Grab the installer for your platform
from the [latest release](https://github.com/sdgriggs01/PaceChart/releases/latest):

- **Windows** — run `PaceChartSetup.exe`. It's a per-user installer that
  requires no admin rights (installs to `%LocalAppData%\Programs\PaceChart`).
- **macOS** — open `PaceChartSetup.dmg` and drag PaceChart into
  Applications. The app isn't code-signed (no Apple Developer account), so
  Gatekeeper will refuse to open it the first time with an "unidentified
  developer" warning. Right-click (or Control-click) the app in Applications
  and choose **Open**, then confirm in the dialog — you only need to do this
  once.
- **Chromebook** — turn on **Linux (Beta)** in Chromebook Settings first
  (Settings → Advanced → Developers), then download `pacechart_*_amd64.deb`
  from the Chromebook's Files app and select **Install with Linux (Beta)**,
  or run `sudo dpkg -i ~/Downloads/pacechart_*_amd64.deb` in the Linux
  terminal. PaceChart then appears in the Chromebook's app launcher. This
  only works on Chromebooks with an Intel/AMD (x86_64) processor, which is
  most of them — ARM-based Chromebooks aren't supported yet.

## Building the installer

A fresh set of installers (Windows, macOS, and Chromebook/Linux) is built
automatically on every push to `master` (see
`.github/workflows/build-installer.yml`), published to the
[latest release](https://github.com/sdgriggs01/PaceChart/releases/latest)
(a rolling build, not a numbered version), and also uploaded as workflow
artifacts. To cut a numbered release instead, bump `version` in
`pyproject.toml` and push a matching `vX.Y.Z` tag (e.g. `v1.0.0`) — the
same workflow builds all three installers and publishes them as that
tagged release.

Each platform's installer must be built on that platform — PyInstaller
doesn't cross-compile — so building locally only produces the installer
for the machine you're on:

```powershell
# Windows
.venv\Scripts\python.exe -m pip install -e ".[build]"
.venv\Scripts\python.exe -m PyInstaller packaging\pacechart.spec --distpath build\dist --workpath build\work --noconfirm
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DMyAppVersion=1.0.0" packaging\installer.iss
```

This needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed
(`winget install JRSoftware.InnoSetup` or `choco install innosetup`). The
resulting `PaceChartSetup.exe` is written to `build\installer\`.

```bash
# macOS
python3 -m pip install -e ".[build]"
python3 -m PyInstaller packaging/pacechart.spec --distpath build/dist --workpath build/work --noconfirm
packaging/macos/build-dmg.sh 1.0.0
```

The resulting `PaceChartSetup.dmg` is written to `build/installer/`.

```bash
# Chromebook Linux (Crostini) / Debian / Ubuntu
python3 -m pip install -e ".[build]"
python3 -m PyInstaller packaging/pacechart.spec --distpath build/dist --workpath build/work --noconfirm
packaging/linux/build-deb.sh 1.0.0
```

The resulting `pacechart_1.0.0_amd64.deb` is written to `build/installer/`.

## Project layout

```
src/pacechart/
  calculator.py   # the pace/equivalent-performance model (see Calculator-Methodology.md)
  models.py       # Athlete, RaceResult, Meet, and the 5k/3k-equivalent averaging logic
  scraper.py      # XC roster/schedule/results page parsing + fetching
  track_scraper.py # track roster/schedule/results parsing + fetching (see Track-Mode-Plan.md)
  app_state.py    # GUI-independent application state (selections, calculation, templates, XC/Track mode)
  templates.py    # persisted pace-selection templates (%APPDATA%\PaceChart\templates.json)
  pdf.py          # PDF report generation
  gui.py          # the Tkinter application
tests/            # pytest suite, with saved HTML fixtures for the scraper tests
```

## License

[MIT](LICENSE)
