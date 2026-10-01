# Aether 0.3 x86_64 desktop build record

This directory holds provenance for the Aether 0.3 desktop pipeline. The
console build (0.1-dev) has a separate build record under `build/images/build-record/`.

- `manifest.txt` — human-readable summary of the build (kernel, toolchain, timestamp)
- `kernel-x86_64.config` — kernel configuration used for the 0.3 desktop build
- `aether_defconfig` — base Aether defconfig snapshot referenced during the build
- `sources.json`, `direct-sources.json`, `extra-sources.json`, `targets.json` — desktop pipeline dependency and target definitions

These files are copied from the build VM's `/opt/aether/desktop/build-record/`
and are not build outputs; they are build inputs/metadata for traceability.
They do not contain secrets or build-time credentials.
