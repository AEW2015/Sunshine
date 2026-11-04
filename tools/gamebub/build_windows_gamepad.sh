#!/usr/bin/env bash
# Build the pinned ViGEm user-mode client only; no driver installation occurs.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"
cmake -S third-party/ViGEmClient -B cmake-build-gamebub-vigem -G Ninja \
  -DViGEmClient_DLL=ON -DCMAKE_BUILD_TYPE=Release \
  '-DCMAKE_SHARED_LINKER_FLAGS=-static -static-libgcc -static-libstdc++'
cmake --build cmake-build-gamebub-vigem --target ViGEmClientShared
