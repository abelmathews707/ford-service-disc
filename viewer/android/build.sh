#!/bin/sh
# Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
#
# Build the offline Android wrapper (FordManual.apk) with the Android SDK
# command-line tools. No Gradle, no Android Studio, no network at build time
# beyond what sdkmanager needs the first time.
#
# Requirements:
#   - JDK 8+ (javac, keytool)
#   - Android SDK command-line tools (sdkmanager) or an existing SDK with
#     platform android-29 and build-tools 29.0.3
#   - zip (present on macOS and most Linuxes)
#
# The SDK location is taken from $ANDROID_HOME, or inferred from sdkmanager
# being on PATH.
#
# Note: dexing uses dx rather than d8. d8 (in every build-tools release we
# tried, 29 through 34) crashes with an internal NPE on the class files this
# wrapper produces under current JDKs; dx handles them fine. dx is deprecated
# but stable and more than enough for a single-activity app.
set -eu

cd "$(dirname "$0")"

OUT=build
KEYSTORE=debug.keystore

# Keep the signing identity outside $OUT, which is recreated on every build.
# Migrate the key produced by older versions of this script if it is present.
if [ ! -f "$KEYSTORE" ] && [ -f "$OUT/debug.keystore" ]; then
  mv "$OUT/debug.keystore" "$KEYSTORE"
fi
rm -rf "$OUT"
mkdir -p "$OUT/classes"

# --- locate the SDK -------------------------------------------------------
if [ -n "${ANDROID_HOME:-}" ]; then
  SDK="$ANDROID_HOME"
elif command -v sdkmanager >/dev/null 2>&1; then
  SDK="$(dirname "$(dirname "$(command -v sdkmanager)")")"
else
  echo "error: Android SDK not found. Set ANDROID_HOME or install the" >&2
  echo "command-line tools (brew install --cask android-commandlinetools)." >&2
  exit 1
fi

PLATFORM="$SDK/platforms/android-29/android.jar"
BUILD_TOOLS="$SDK/build-tools/29.0.3"
AAPT2="$BUILD_TOOLS/aapt2"
DX="$BUILD_TOOLS/dx"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"

if [ ! -f "$PLATFORM" ] || [ ! -x "$AAPT2" ]; then
  if command -v sdkmanager >/dev/null 2>&1; then
    echo "Installing platform android-29 + build-tools 29.0.3 (first run only)..."
    yes | sdkmanager "platforms;android-29" "build-tools;29.0.3" >/dev/null
  else
    echo "error: missing $PLATFORM or $AAPT2; install them with:" >&2
    echo "  sdkmanager "platforms;android-29" "build-tools;29.0.3"" >&2
    exit 1
  fi
fi

# --- assemble -------------------------------------------------------------
echo "aapt2 compile/link..."
"$AAPT2" compile --dir res -o "$OUT/res.zip"
"$AAPT2" link -o "$OUT/base.apk" -I "$PLATFORM" \
  --manifest AndroidManifest.xml -R "$OUT/res.zip" --auto-add-overlay \
  --min-sdk-version 26 --target-sdk-version 29

echo "javac..."
javac --release 8 -classpath "$PLATFORM" -d "$OUT/classes" \
  src/com/fordservicedisc/viewer/MainActivity.java \
  src/com/fordservicedisc/viewer/LoopbackHttpServer.java

echo "dx (dex)..."
"$DX" --dex --output="$OUT/classes.dex" "$OUT/classes"

echo "package + align + sign..."
(cd "$OUT" && zip -qj base.apk classes.dex)
"$ZIPALIGN" -f 4 "$OUT/base.apk" "$OUT/aligned.apk"

if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -keystore "$KEYSTORE" -alias debug \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android \
    -dname "CN=ford-service-disc debug" >/dev/null 2>&1
fi
"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android \
  --key-pass pass:android --out "$OUT/FordManual.apk" "$OUT/aligned.apk"

echo
echo "Built: viewer/android/$OUT/FordManual.apk"
echo "Install: adb install -r $OUT/FordManual.apk   (or copy to the device and tap)"
