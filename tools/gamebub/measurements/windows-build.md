# Windows tray-free baseline build

This is a **stock Sunshine baseline without the tray**, not a
Game Bub streaming mode. It retains Sunshine's normal HTTP/Web UI and pairing
code. No service, installer, or files under the existing Sunshine installation
were changed. It cannot transmit MSV1 JPEG or provide Game Bub audio/input.

The source used for configuration was Sunshine branch `gamebub/host` at
`027c59412f19674616a3c31af346320a82e75207` with uncommitted changes only under
`tools/gamebub`; the compiler embeds `027c5941-dirty` as the version. Later
commits on the branch changed only that laboratory directory, not native sources.
Build directory: `C:\ai\sunshine-gamebub\cmake-build-gamebub`.

Toolchain installed for this build:

- MSYS2 base `2026-09-27`, x86-64, archive SHA-256
  `ea2f31a0b6ade63914ce441ffb022f0f6aa96982bfefa2326460a26d5fb01322`,
  checked against the official release asset digest.
- UCRT64 GCC `16.2.0-6`, CMake `4.4.5-1`, Ninja `1.13.2-1`, Boost `1.92.0-4`,
  OpenSSL `3.6.5-1`, Opus `1.6.1-2`, libvpl `2.17.0-1`, MinHook `1.3.4-2`.
- Native Windows Node.js `24.22.0`, portable archive SHA-256
  `f9683a19877e12a9b167305c8db71040d812876359de21f0d2e97c3f321f80c3`,
  checked against Node's published SHA-256 list. Rust `1.99.1-1` is needed
  only for the optional receiver-parser integration test.
- Sunshine build-deps FFmpeg release `v2026.1017.131201`, obtained by CMake.

MSYS2 packages are rolling: the versions above record the observed build and
must be retained or obtained from an archive to recreate the same toolchain.
Native Node.js was extracted under ignored `tools/gamebub/artifacts/node/`.

The configure command used:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S . -B cmake-build-gamebub -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON -DBUILD_DOCS=OFF -DSUNSHINE_ENABLE_TRAY=OFF -DCUDA_FAIL_ON_MISSING=OFF -DNPM=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/node/node-v24.22.0-win-x64/npm.cmd -DDOTNET_EXECUTABLE='
```

Configuration completed after making the pinned nested submodules available.
WiX is intentionally skipped because this machine has a .NET runtime without an
SDK; this build is not an installer. Build and test commands:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub --target sunshine test_sunshine --parallel 4'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe'
```

The build completed successfully. The native test executable ran 859 tests:
848 passed and 11 were skipped (including disabled tray and unavailable virtual
HID broker cases); none failed. The unstripped `sunshine.exe` is 184,151,501
bytes, SHA-256 `c1386d215c9af704056011faf72cfa4d93da30d784bedcca34af29503bb47049`.
This is a baseline size, not a measurement of a completed slim product.
The installed service is a separate process and remained running.
