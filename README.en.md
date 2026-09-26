<div align="center">
  <img src="logo.png" alt="Wardogs Mortar Calculator Logo" width="120" height="120" />

  # Wardogs Mortar Calculator

  **A compact tactical HUD overlay for automatic mortar azimuth, distance, and elevation (`mil`) calculation in WARDOGS.**

  [![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d4?style=flat-square&logo=windows&logoColor=white)](#system-requirements)
  [![Python](https://img.shields.io/badge/Python-3.11%2B-38bdf8?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
  [![License](https://img.shields.io/badge/License-MIT-fbbf24?style=flat-square)](LICENSE)

  <p><a href="README.md"><b>🇷🇺 Русский</b></a> &nbsp;|&nbsp; <b>🇬🇧 English</b></p>
</div>

---

## About the Project

**Wardogs Mortar Calculator** is a lightweight on-screen HUD overlay designed for calculating mortar firing parameters in **WARDOGS**. With a single hotkey press, the utility captures a small region around your mouse cursor on the in-game tactical map, reads the current crosshair coordinates (`X` / `Y`) using the native Windows OCR engine, and instantaneously computes the firing solution for your mortar.

### Key Features
* **Click-Through Overlay Mode** — The HUD window stays on top of the game while passing all mouse clicks and movements directly through to the game without interrupting gameplay.
* **Instant Ballistic Calculation** — Automatically computes azimuth accurate to `0.1°`, distance in meters, and sight elevation in `mil` (effective firing range `80–684 m`).
* **Customizable Interface & Bilingual UI** — Adjustable window opacity (`20%–100%`), configurable cursor capture box size, free drag-and-drop HUD positioning, live OCR capture preview, and instant switching between **Russian (`RU`)** and **English (`EN`)** interface languages.
* **Custom Keybindings** — One-click hotkey rebinding supporting keyboard keys (`F1–F12`, `A–Z`, `0–9`, `NumPad`, modifiers) as well as extra mouse buttons (`MOUSE4`, `MOUSE5`, `MMB`).
* **Minimal Resource Footprint** — Powered by native Windows libraries for sub-second response times, consuming only around `22 MB` of RAM and `0%` CPU when idle.

---

## Live Demonstration

<div align="center">
  <img src="docs/demo.gif" alt="Wardogs Mortar Calculator in-game demonstration" width="820" />
  <p><i>Instant capture of mortar and target coordinates directly on the tactical map</i></p>
</div>

### Interface Screenshots

| Combat Mode (In-Game Overlay) | Settings & Keybinding Mode |
| :---: | :---: |
| <img src="docs/screenshot_combat.png" alt="Combat Mode HUD" width="400" /> | <img src="docs/screenshot_settings.png" alt="Settings Mode F3" width="400" /> |

---

## Fair Play Policy & Security

**Wardogs Mortar Calculator is NOT a cheat, game modification, or unauthorized exploit.**

* This software serves as an external quality-of-life assistive utility — a functional counterpart to standard community web artillery calculators that eliminates the need to `Alt+Tab` out of the game or manually type coordinates into a second monitor or smartphone.
* The application operates strictly as an independent Windows desktop tool. It does **not** inject code, **not** modify game executables or files, **not** intercept network traffic, and **not** read or write process memory.
* Coordinate recognition is performed purely via optical character recognition (OCR) from the screen buffer around the mouse cursor — reading the exact same visual information that a player sees with their own eyes.
* Because the tool does not interact with game memory or files, it does not trigger memory-signature anti-cheat detections. However, this project is an independent community-made utility: the developer is not affiliated with the creators of WARDOGS and assumes no responsibility for changes to third-party platform terms of service or end-user license agreements.

---

## System Requirements

* **Operating System:** Windows 10 (build 1809 or newer) / Windows 11 (64-bit).
* **Windows OCR Language Pack:** The **English** language pack with Optical Character Recognition support must be installed in Windows so that the native `Windows.Media.Ocr` component can function *(Windows Settings → Time & Language → Language & Region)*.
* **In-Game Display Mode:** **Borderless Windowed** or **Windowed**. Exclusive Fullscreen mode prevents third-party Windows overlays from rendering on top of the game.
* **Permissions:** If the game client runs as Administrator, the calculator must also be launched as Administrator so global hotkeys can register properly while the game window is focused.

---

## Controls

| Default Hotkey | Action | Description |
| :---: | :--- | :--- |
| **`F1`** | **Mortar Position** | Captures `X` and `Y` coordinates around the mouse cursor and saves your mortar's firing position. |
| **`F2`** | **Target Position** | Captures target `X` and `Y` coordinates and immediately computes **Azimuth (`°`)**, **Elevation (`mil`)**, and **Distance (`m`)**. |
| **`F3`** | **Settings Mode** | Toggles the overlay between click-through combat mode and interactive settings mode (window positioning, opacity, language selection `RU`/`EN`, manual coordinate input, and hotkey rebinding). |
| **`F4`** | **Hide / Show HUD** | Hides or restores the overlay window on screen. |

---

## Installation & Usage

### Standalone Executable (Recommended)
1. Download the latest release executable from the [**Releases**](../../releases) page.
2. Run `WarDogs_Calculator.exe` (no Python installation or external dependencies required).

### Running from Source

> **Requirement:** [Python 3.11+](https://www.python.org/downloads/) installed (make sure to check **"Add python.exe to PATH"** during installation).

```powershell
git clone https://github.com/ProDexortie/wardogs-mortar-calculator.git
cd wardogs-mortar-calculator

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python main_lite.py
```

---

## Building from Source

To compile a standalone `.exe` binary (using `build_exe.bat` or manually via PyInstaller):
```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name WarDogs_Calculator --icon="icon.ico" --add-data "icon.ico;." --add-data "logo.png;." main_lite.py
```

---

## License

Distributed under the [MIT License](LICENSE).
