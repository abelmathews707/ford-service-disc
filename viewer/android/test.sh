#!/bin/sh
# Copyright (c) 2026 Alexander Hill. SPDX-License-Identifier: MIT
set -eu

cd "$(dirname "$0")"

OUT=build/test-classes
rm -rf "$OUT"
mkdir -p "$OUT"

javac --release 8 -Xlint:-options -d "$OUT" \
  src/com/fordservicedisc/viewer/LoopbackHttpServer.java \
  test/com/fordservicedisc/viewer/LoopbackHttpServerTest.java

java -cp "$OUT" com.fordservicedisc.viewer.LoopbackHttpServerTest
