# Solar Sound System Simulator — macOS Build

This folder contains everything needed to produce a native macOS `.dmg` installer from the Python source.

> **No Mac? No problem.**  
> A GitHub Actions workflow (`.github/workflows/build_mac.yml`) automatically builds the `.dmg` on Apple hardware every time you push to `main`.  
> Download it from the **Actions → Artifacts** tab at `https://github.com/AlleeCabral/SolarMobileSoundSystem/actions`  
> or attach it to a permanent release by pushing a version tag: `git tag v1.0 && git push origin v1.0`

---

## What you need (to build locally on a Mac)

> If you do not have a Mac, skip this section — use GitHub Actions instead (see note above).

| Requirement | Notes |
|---|---|
| **macOS 11 Big Sur or newer** | Older versions may work but are untested |
| **Python 3.9 – 3.12 (system or Homebrew)** | Must include Tkinter. Check: `python3 -c "import tkinter"` |
| **py2app** | Install once — see below |
| **Xcode Command Line Tools** | `xcode-select --install` |

---

## One-time setup (local Mac build)

```bash
# 1. Install py2app into the project's venv (or system Python)
cd /path/to/Bike          # the repo root
python3 -m venv .venv
source .venv/bin/activate
pip install py2app
```

> **Tkinter on macOS**  
> The macOS system Python **does not** include Tkinter.  
> Use the [python.org installer](https://www.python.org/downloads/macos/) (includes Tk)  
> or Homebrew: `brew install python-tk@3.12`

---

## Build the .dmg (local Mac build)

```bash
cd ForMac
chmod +x build_dmg.sh
./build_dmg.sh
```

The script will:
1. Run `py2app` to bundle `app.py` + `rules_engine.py` + `simulate.py` into `ForMac/dist/Solar Sound System Simulator.app`
2. Create a drag-and-drop `.dmg` at `ForMac/dist/SolarSoundSimulator.dmg`

---

## Install

1. Open `SolarSoundSimulator.dmg`
2. Drag **Solar Sound System Simulator** into the **Applications** folder shortcut
3. Eject the disk image
4. Launch from Applications or Spotlight

---

## First-launch Gatekeeper warning

Because the app is not notarized with Apple, macOS may block it the first time.  
To allow it:  
- Right-click the app → **Open** → **Open** (one-time confirmation), or  
- System Settings → Privacy & Security → scroll down → **Open Anyway**

---

## File layout after build

```
ForMac/
├── setup.py           # py2app configuration
├── build_dmg.sh       # build + package script
├── README_mac.md      # this file
├── AppIcon.icns       # (optional) place your icon here before building
├── build/             # intermediate py2app output (auto-created)
└── dist/
    ├── Solar Sound System Simulator.app
    └── SolarSoundSimulator.dmg   ← distribute this
```

---

## Adding a custom icon (optional)

1. Create a 1024 × 1024 px PNG of your icon.
2. Convert it to `.icns`:
   ```bash
   mkdir icon.iconset
   sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
   # (repeat for other sizes if desired)
   iconutil -c icns icon.iconset -o ForMac/AppIcon.icns
   ```
3. Re-run `./build_dmg.sh` — the icon will be embedded in the `.app`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `import tkinter` fails | Use python.org Python or `brew install python-tk@3.12` |
| `py2app` not found | Run `pip install py2app` inside your active venv |
| App opens then immediately closes | Run from Terminal to see the error: `open -a "Solar Sound System Simulator" --args` |
| Gatekeeper blocks permanently | See Gatekeeper section above |
