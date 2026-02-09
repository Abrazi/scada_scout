#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="/tmp/libiec61850_build"

if ! command -v cmake >/dev/null 2>&1; then
  echo "cmake not found. Install with: sudo apt-get install cmake build-essential" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git not found. Install with: sudo apt-get install git" >&2
  exit 1
fi

if ! command -v make >/dev/null 2>&1; then
  echo "make not found. Install with: sudo apt-get install build-essential" >&2
  exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
git clone https://github.com/mz-automation/libiec61850.git "$BUILD_DIR/libiec61850"
mkdir -p "$BUILD_DIR/libiec61850/build"
cd "$BUILD_DIR/libiec61850/build"
cmake ..
make -j"$(nproc)"

cp "$BUILD_DIR/libiec61850/build/src/libiec61850.so" "$ROOT_DIR/lib/"

echo "Copied libiec61850.so to $ROOT_DIR/lib/"
