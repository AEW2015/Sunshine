#!/usr/bin/env bash
# Build only the offline v20 replay executable; never install or start Sunshine.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"
cmake -S tools/gamebub/native -B cmake-build-gamebub-v20 -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build cmake-build-gamebub-v20
