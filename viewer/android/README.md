# Offline Android wrapper

A tiny WebView app that shows a built manual site fully offline on an Android
tablet or phone. The bundled viewer makes no external requests. No Gradle.

## Why this exists

The viewer is a single-page app that loads its content with `fetch()`. If
you open `index.html` straight from local storage in a normal browser, the
browser blocks those requests — `file://` pages are not allowed to fetch
other local files. And current Android WebView ignores the legacy "allow
file access from file URLs" switches, so a plain file:// wrapper just sits
on the loading screen.

This wrapper runs a real HTTP server on an ephemeral `127.0.0.1` port and
serves files from `/sdcard/FordManual/`. Same-origin `fetch()` then works even
on older WebViews that do not reliably intercept virtual-origin requests.
The server cannot accept connections from another device or network interface.

It contains no content. It is a small shell around whatever you put in
`/sdcard/FordManual/`.

## Test

The loopback server has a pure-Java socket-level regression harness, so it can
be tested without Android or an emulator:

```sh
./viewer/android/test.sh
```

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

Targets Android 8.0+ (API 26) with `targetSdk 29`; this matches the Android
version on the diagnostic tablets (XTool D7 class) the wrapper was written
for. The viewer stays within ES2019 syntax for Android 10 XTool D7 tablets
whose WebView identifies as Chrome 74. The HTTP server binds only to
`127.0.0.1`, so it is not reachable through another device or network
interface. Android 10 WebView 91 requires the app's base cleartext opt-in to
load even this local HTTP origin; a domain-only exception for `127.0.0.1` or
`localhost` does not work there. The cleartext opt-in is therefore app-wide,
while the server remains loopback-only.
