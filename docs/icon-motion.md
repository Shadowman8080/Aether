# Click animation

Vector animates application, file and Places icons with a brief inward pulse
and return. Both mouse clicks and keyboard activation trigger it. Labels,
selection and hit areas stay in place; actions are not delayed. Only the most
recently activated item in each view animates, with no idle timer.

The desktop power button has a matching press animation. Its menu opens
immediately. Standard Plasma dock icons and third-party applications are not
modified by this change.

Vector reads `KDE/AnimationDurationFactor` from the user's `kdeglobals` each time
an animation starts. Zero disables motion. The power button uses Kirigami's
standard animation durations. Existing system animation preferences are not
overwritten.

## Validation

Compiled using Aether's native Qt/KDE toolchain on the Ubuntu build VM with all
16 available CPUs. Build with `-DAETHER_TEST_ICON_MOTION=ON` to enable the
`test-icon-motion` executable. Run with `QT_QPA_PLATFORM=offscreen`, then repeat
with `QT_SCALE_FACTOR=2`.

Both scales passed: a visibly different intermediate frame, exact return to the
original frame, no motion when disabled, and safe repeated activation followed
by model reset. Power QML lint reported contextual `i18n` warnings already
present in the component; no new animation-related diagnostics.

The user installation package preserves the system copy of Vector and the
power plasmoid, installing user overrides with backups. The user confirmed the animation package works in their VMware desktop.
The unified image rebuild is tracked in [release verification](release-20261006.md).
