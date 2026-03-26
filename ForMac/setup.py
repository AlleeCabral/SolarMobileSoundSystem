"""
py2app build script for Solar Sound System Simulator.

Build the .app bundle:
    python setup.py py2app

Then run build_dmg.sh to wrap it into a .dmg.
"""

from setuptools import setup

APP = ["../app.py"]
DATA_FILES = [
    ("", ["../rules_engine.py", "../simulate.py", "../my_system.json"]),
]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "AppIcon.icns",   # place your icon here (optional)
    "plist": {
        "CFBundleName":             "Solar Sound System Simulator",
        "CFBundleDisplayName":      "Solar Sound System Simulator",
        "CFBundleIdentifier":       "com.yourname.solarsoundsim",
        "CFBundleVersion":          "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHumanReadableCopyright": "© 2026",
        "NSHighResolutionCapable":  True,
    },
    "packages": [],          # stdlib only — nothing extra needed
    "excludes": ["pytest", "setuptools", "pip"],
}

setup(
    name="SolarSoundSimulator",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
