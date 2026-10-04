# Duel Links PC Bot
Simple bot with GUI using AutoIt language for farming Duel Links on PC/Steam.

## Local build

The repository includes a local build script. Install the AutoIt compiler and SciTE wrapper once:

```powershell
winget install --id AutoIt.AutoIt --exact
winget install --id AutoIt.SciTE4AutoIt3 --exact
```

Then build the executable without creating a Git tag or GitHub release:

```powershell
powershell -ExecutionPolicy Bypass -File .\build-local.ps1
```

The executable and runtime files are written to `dist\`. The script runs the repository contract tests before compiling.

## MuMu emulator mode

For normal use, run the bot with MuMu 12 and the Android version of Duel Links. The bot auto-detects one connected ADB device, captures the emulator with `adb exec-out screencap -p`, and taps with `adb shell input tap`, so it can keep farming while the emulator is in the background.

Recommended emulator display:

- portrait `720x1280`
- ADB/debugging enabled in MuMu
- exactly one emulator instance connected

No environment variables are required for the bundled package. For local development, the bot looks for ADB in this order: package directory, `platform-tools\adb.exe`, `E:\Android\android-sdk\platform-tools\adb.exe`, then `adb` from `PATH`.

**Feature**
  - Gate duel: duel any available legendary duelist in the gate.
  - Street duel: duel any duelist in the street and pickup loot
  - Collect gems in the scenery.
  - Event Specific
	- Battle City Showdown
		- Auto pick Card Lottery -
		- Bot farm Devine Trial Yami Yugi Lv. 50
		- Bot play City Showdown track


## Tutorial

1. Start MuMu 12 and enable ADB/debugging.
2. Set MuMu display to portrait `720x1280`.
3. Open the Android version of Duel Links and log in.
4. Start `duel-links-bot.exe` and click Start Duel.

The legacy Steam/window mode is still available as a fallback when no emulator is connected, but the recommended path is MuMu background mode.

## Screenshot

![image](https://github.com/ftuyama/duel-links-bot/assets/11530478/e37cbdb2-2939-49e0-a686-4d1d2494bf0d)
