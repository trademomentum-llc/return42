#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../cliniclink-desktop"
npm ci
cargo tauri build
