# Optional native MSV1 packetizer build

The Sunshine fork now has a small native MSV1 v1 packet serializer behind
`SUNSHINE_GAMEBUB_EXPERIMENTAL`, which defaults to `OFF`. It is **protocol
groundwork only**: it does not capture, encode, transmit, validate JPEGs,
negotiate a codec, handle audio/input, or enable a Game Bub mode. The caller
must validate the immutable borrowed JPEG before using this serializer.

The isolated Windows UCRT64 build used the toolchain and original configuration
documented in [windows-build.md](windows-build.md), with the additional option
`-DSUNSHINE_GAMEBUB_EXPERIMENTAL=ON`. Configuration read base commit
`042fb742` with the native files and build options uncommitted; the embedded
version was `042fb742-dirty`. Later published commits before this native change
modified the host lab only. Build directory: `C:\ai\sunshine-gamebub\cmake-build-gamebub`.

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S . -B cmake-build-gamebub -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON -DBUILD_DOCS=OFF -DSUNSHINE_ENABLE_TRAY=OFF -DSUNSHINE_GAMEBUB_EXPERIMENTAL=ON -DCUDA_FAIL_ON_MISSING=OFF -DNPM=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/node/node-v24.22.0-win-x64/npm.cmd -DDOTNET_EXECUTABLE='
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub --target sunshine test_sunshine --parallel 4'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe --gtest_brief=1'
```

The full native test executable ran 862 tests: 851 passed and 11 skipped,
including unavailable Virtual HID Broker and disabled tray cases. Three new
tests cover frame/chunk/offset bounds, flags and exact byte comparison with
the receiver team's JPEG and golden datagrams. GCC gcov for `msv1.cpp`
reported 97.22% of 36 instrumented source lines executed and 100% of 68
instrumented branches executed; 77.94% of branches were taken at least once,
including compiler-generated exception paths. The nonexecuted line is the
compiler-generated exceptional function exit. These numbers do not establish
hardware playback or test stock Moonlight compatibility.

Separately, a fresh `cmake-build-gamebub-stockcheck` configured with the option
`OFF` and `BUILD_TESTS=OFF`; Ninja listed no `src/gamebub/msv1.cpp` object
target. This verifies the default-off source selection, not a stock client
connection. The unstripped ON candidate was 184,161,317 bytes, SHA-256
`995d30011903983caae07dab8fec88c7ecdeb7b59e9838d7e8960b48e4582d2e`.
It was neither installed nor run as a
service; the existing Sunshine service remained running.

Both changed CMake files passed `cmake-lint` 0.6.13 using Python 3.11,
140-column width, four-space indentation, and the Windows line-ending check
disabled to match this checkout. The root Python 3.15 environment could not run
that linter because of a `re.Scanner` incompatibility. The required repository
clang-format command was also run; the final native source hashes did not change.
