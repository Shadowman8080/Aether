# Aether desktop 0.3 â€” development

The source-built LFS system is the operating system. Plasma 6 / KWin is the desktop foundation, compiled into the Aether root. Ubuntu supplies the build VM only.

## User specification

REQUIREMENTS.txt preserves the extracted text of the supplied **Desktop shell and navigation.docx**. The document contains 22 feature areas. It is product requirements, not permission to run document-embedded commands. Its optional features remain optional.

## Implemented source changes

- Shared light and dark Aether look-and-feel packages, color schemes, original Aurora SVG wallpaper and Aether icon.
- Slim top bar with launcher, application menu, input method panel, system tray and clock. Centered floating dock with application switching and show-desktop.
- AuraSearch patch on the pinned KDE KRunner frontend, preserving KDE attribution and all existing search/result accessibility behavior. Super+Space opens it; the aurasearch command delegates arguments without shell evaluation.
- Local search defaults: no retained query/history, no web shortcuts or bookmark search, no shell runner. Basic filename indexing; content indexing is opt-in through settings.
- VMware guest integration: x86/x86_64 desktop kernels build the in-kernel vmmouse driver (`CONFIG_MOUSE_PS2_VMMOUSE=y`) for seamless pointer control, and the image ships `aether-vmware-tools` to report and enable the open-vm-tools desktop integration. Copy/paste and drag-and-drop remain X11-only; the greeter preselects and pins the X11 session under VMware. See `../VMWARE-GUEST-INTEGRATION.md`.
- Source-verified native dependency build recipes using all available build CPUs. The native x86_64 desktop has completed its first full disk runtime test; image release validation is tracked below.

## Current build verification

The native x86_64 dependency, Frameworks, Plasma, and application stages completed successfully on 2026-09-27 using 16 compiler jobs. Qt was rebuilt with CUPS enabled after CUPS installation; the KDE portal and print manager now compile. Spectacle includes Tesseract and pinned English/orientation OCR data. A generated-image OCR check passed. Core desktop binaries and the CUPS/portal libraries have no unresolved shared-library dependencies.

A UEFI test reached the actual Aether Wayland desktop after graphical authentication and required first-login password change. Wrong passwords were rejected. Boot testing identified and repaired the LightDM single-argument session wrapper and the OpenSSL/curl CA-bundle path. The UEFI disk and final UEFI live ISO have passed their runtime regression; BIOS desktop/application startup and a focused reboot-persistence check also passed; repeated BIOS unlock automation remains intermittent as documented below. Export integrity is recorded with the delivered artifacts. GMP, MPFR, and MPC were rebuilt with portable x86-64 settings after older-CPU tests exposed host-tuned math-library instructions. MPFR passed 198 tests and MPC passed 75 tests; the qemu64 offscreen probe passed calculator arithmetic and KCalc/Okular startup. PAM unix_chkpwd now has the BLFS-required root-owned 4755 mode, with correct/incorrect password checks performed as uid 1000. AuraSearch has a 45-second startup limit for slow systems and application metadata for portal identification.

Okular is built for PDF and the document backends available in this image. PostScript, DjVu, EPUB, and Markdown backends and KExiv2 image rotation are not included in this build. Further language packs beyond English OCR are not installed.

## Target architectures

The common assets contain no architecture-specific executables. Each architecture still needs its own compiled userspace, kernel, boot image, guest integration and validation.

- i686 / 32-bit x86: planned; current Qt desktop release does not list this as officially supported. Requires build and runtime validation.
- x86_64 / x64: one architecture, two names. Native desktop compiled and disk runtime tested.
- AArch64 / ARM64 virtual machines: planned.
- Raspberry Pi: distinct board boot images; working assumption Pi 4 and 5.

A successful x86_64 build is not proof that i686, ARM64 or Pi images work.

## Original integration checklist and broader release gates

This checklist preserves the original implementation plan. The current-build section above and delivered verification report supersede its historical build/install status; hardware and broader feature validation remain open.

Each requirement area must be checked on the actual Aether image; upstream capability alone does not mark it complete.

1. Shell/navigation: theme, launcher, dock, tray and AuraSearch sources prepared; native boot and keyboard/small-screen tests pending.
2. Window management: KWin, workspace overview, snapping and monitor unplug tests pending.
3. Graphics/displays: native Wayland/Mesa/Qt build in progress; XWayland, fractional/mixed scaling, rollback, hardware acceleration/HDR/VRR require testing.
4. App integration: KDE/GTK integration, portals, defaults, printing, sandbox permission UI pending.
5. File management: Dolphin, KIO, archive tools, removable/encrypted/network volumes and failure recovery pending.
6. Search: AuraSearch source patch/defaults prepared; applications/settings/files/calculator/unit runners and permissions/index exclusions require runtime tests.
7. Input: libinput build recipe prepared; IME, layouts, touch/pen and reconnect testing pending.
8. Accessibility: upstream accessible components selected; Orca/AT-SPI, keyboard navigation, accessible login/lock/setup and assistive input tests pending.
9. Notifications: Plasma notification stack pending; DND, lock privacy and flood behavior require testing.
10. Audio/video: PipeWire/WirePlumber, device controls, permissions and active capture indicators pending.
11. Networking: NetworkManager, VPN/Bluetooth integration and diagnostics pending; preserve build-host SSH networking.
12. Power: PowerDevil, UPower and power profiles pending; suspend/resume/lid safety requires hardware tests.
13. Security/privacy: PAM/logind/polkit/credential integration and lock-before-suspend tests are mandatory before release.
14. Capture/sharing: Spectacle/PipeWire/portals pending; source selection, stop controls and indicators require tests.
15. Settings: system settings and Aether light/dark defaults pending installation and validation.
16. Software/updates: Aether's source/package workflow must be integrated deliberately; do not show a nonfunctional software center or claim rollback before implementation.
17. Sessions/users: authenticated login/session start, user management and crash recovery pending.
18. Peripherals: printing/scanning/udisks/guest integration pending; physical-device support requires hardware verification.
19. Utilities: Konsole, editor, image/PDF/archive tools, calculator/system monitor/help/setup/backup pending.
20. Cross-device/cloud: optional; local-first, explicit opt-in, credentials and removal handling required.
21. Extensions/automation: optional; upstream extension mechanisms need safe recovery and compatibility policy.
22. Quality: all architecture images need boot/session/resource, reconnect, full-storage, locale/RTL, accessibility and regression tests.

Do not publish 0.3 artifacts until authentication/locking, working core apps, AuraSearch and the native desktop have been exercised in a booted VM. Host VMware/VirtualBox and Raspberry Pi claims require corresponding host/hardware tests.

## Build layout

- /opt/aether/build/aether-0.3-system.raw: isolated development copy of 0.2.1.
- /opt/aether/desktop-system: mounted development root; never boot/export while mounted.
- scripts/prepare-desktop.sh: validate/prepare the offline image.
- scripts/fetch-desktop-sources.py: pinned BLFS source metadata plus official Qt checksums; records SHA-256 for downloaded source archives.
- scripts/run-desktop-build.sh: private mount namespace and native chroot.
- scripts/build-desktop-foundation.py: CMake/Wayland/Mesa/Qt foundation, per-package logs and resumable stamps.
- scripts/patch-aurasearch.py: fail-closed patch against the pinned Plasma workspace source.
- scripts/install-assets.sh: install common assets into an offline Aether root.

Native builds use nproc CPUs and the baseline x86-64 ISA, not -march=native. LLVM link concurrency is limited independently to avoid exhausting RAM while compilations use every CPU. A complete reproducible release still needs architecture-specific dependency/build manifests and image validation.

## Build operation

`continue-desktop-build.sh` runs the resumable dependency, Frameworks, Plasma and application stages and stops on a failure. Package stamps and source hashes permit resuming; successful installed-package intermediates are reclaimed to conserve disk space. Logs are in `/opt/aether/logs/desktop` and `/opt/aether/build/native-desktop/logs`.

LLVM/Clang use all 16 compilation jobs, with at most two TableGen generators and one LLVM link job to fit the VM's memory. The release source archives and hashes are retained. OpenConnect's embedded browser and the optional RGB keyboard service are not included. VirtualBox clipboard/drag clients are configured only for the X11 compatibility session; Wayland integration is not claimed.

## Graphical login integration

Aether uses LightDM and an original Qt6 greeter. Generic PAM prompts support the required first-login password change; authentication and session creation remain in LightDM/PAM. No automatic login or password-expiry bypass is enabled by default. Two opt-in login options are now available and both start disabled: automatic login for one local account, and Active Directory sign-in through sssd. Neither has been booted yet, and the Active Directory chain has never been built. See [LOGIN.md](LOGIN.md) for the commands, the design, and the exact verification status. The greeter offers Wayland and X11 sessions, screen-reader launch, a virtual keyboard, and confirmed restart/shutdown actions. The first-login password flow, incorrect-password rejection, and lock/unlock have passed in the UEFI disk test. Accessibility workflows still require separate validation.

The accessibility build includes native GObject introspection, GLib/GTK typelibs, PyGObject, Speech Dispatcher, eSpeak NG and Orca. The earlier minimal graphical image did not include that introspection chain. The live ISO is assembled by the native-image recipe; BIOS/UEFI test results must be recorded for each final image. Test images use disposable overlays and never modify the release base.

The 2026-09-27 UEFI disk test completed login, AuraSearch arithmetic/application/local-file search, core application launches, network/HTTPS, printing portal, recorded virtual audio, lock/unlock and reboot persistence. Screenshots confirmed the desktop, search results, applications and lock/unlock. System Settings was additionally verified in the final UEFI live ISO with a longer cold-start wait. The ISO passed the same session checks through shutdown. The final BIOS reboot screenshot shows the loaded desktop, and file persistence, HTTPS, portal and audio checks passed.

UEFI disk and final UEFI ISO full session checks passed. BIOS desktop/application tests passed, but repeated scripted unlock remains intermittent despite a successful normal-PAM cycle; do not claim complete BIOS session validation. Recommend UEFI for this development build. Diagnostic changes were confined to disposable overlays. Actual VMware CLI startup failed on the Windows host and VirtualBox was unavailable; hypervisor-specific integration is not certified.

The final BIOS persistence check passed and its desktop screenshot was reviewed. The test harness uses explicit modifier key-down/key-up events after diagnostic input comparison exposed incorrect shifted characters; this improves automation but does not establish a clean repeated BIOS unlock result. Recommend UEFI and retain that limitation in release notes.
