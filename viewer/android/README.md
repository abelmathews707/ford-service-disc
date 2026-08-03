# Offline Android wrapper

A tiny WebView app (~150 lines) that shows a built manual site fully offline
on an Android tablet or phone. No network, no server, no Gradle.

## Why this exists

The viewer is a single-page app that loads its content with `fetch()`. If
you open `index.html` straight from local storage in a normal browser, the
browser blocks those requests — `file://` pages are not allowed to fetch
other local files. This wrapper enables file access in its own WebView and
points it at a local copy, which sidesteps that entirely.

It contains no content and fetches nothing from the network. It is a 13 KB
shell around whatever you put in `/sdcard/FordManual/`.

## Build

You need a JDK and the Android SDK command-line tools (no Android Studio):

```sh
brew install --cask android-commandlinetools   # macOS
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
./viewer/android/build.sh
```

The script installs platform 29 and build-tools 29.0.3 on first run, then
produces `viewer/android/build/FordManual.apk`.

## Put the manual on the device

Build the site normally, then copy it to the tablet. Either push over USB:

```sh
python3 -m fsd all /Volumes/20SLB -o site
adb push site /sdcard/FordManual
```

or, on a device with an FTP server (many diagnostic tablets have one), upload
the contents of `site/` to the `FordManual` folder on the device.

## Install and run

1. Copy `FordManual.apk` to the device and tap it (allow "install unknown
   apps" when prompted), or `adb install -r FordManual.apk`.
2. Grant storage access when the app asks.
3. Open **Ford Service Manual**. Everything — search, wiring diagrams,
   connector views, PCED — works with no internet connection.

Targets Android 8.0+ (API 26) with `targetSdk 29`, which is what lets the
WebView read local files; this matches the Android version on the diagnostic
tablets (XTool D7 class) the wrapper was written for.
