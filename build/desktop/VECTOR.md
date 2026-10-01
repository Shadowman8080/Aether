# Vector desktop integration

Vector is Aether's native Qt/KDE application browser. It opens to an alphabetical
Applications view with category filters, search, icon/list views and application
launching through KDE's launch service. A Favorites sidebar browses home folders;
files open in their associated applications. This first version browses and opens
files; it does not yet implement copy/move/delete operations inside Vector.

The light and dark default layouts remove the top-panel application launcher and
place Vector immediately after AuraSearch in the bottom dock. The migration in
`assets/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aether-vector.js`
provides a fallback migration. The pre-session helper in `assets/usr/libexec/aether-vector-migrate.py` updates existing accounts before Plasma starts, so panel edits finish before its views are created. It preserves other settings, backs up changed configuration files, and runs once per account. It replaces the dock's
Dolphin shortcut with Vector and preserves other pins/widgets. Dolphin remains
installed and can be launched from Vector for advanced file operations.

Keyboard controls: Ctrl+F searches, Enter selects the first application result,
Enter again opens it, Ctrl+1/Ctrl+2 switch icon/list view, Alt+Left/Right navigate
history, Alt+Up opens the enclosing folder, Ctrl+L edits the location, F5 refreshes
the application catalog. Hidden/non-menu applications are excluded.

Build with `scripts/build-vector.py` inside the native Aether desktop build root.
The normal application build stage calls this recipe. It uses all available CPUs
and requires Qt6 Widgets, KF6 Service and KF6 KIO. The source has no architecture
specific code; only x86_64 has been compiled so far.

## Verification checkpoint

The native x86_64 release build passes using all 16 available build CPUs. Native
search/navigation smoke tests, both-theme default layout checks, idempotent
migration checks, and graphical application launch checks pass. A fresh-account
UEFI desktop boot shows Vector next to AuraSearch and no top-panel Start button.
BIOS and UEFI live ISO boot, required-service checks, and clean shutdown pass.
A duplicate zram swap shutdown operation was fixed in the security recipe and images.

Existing-account migration now runs before Plasma starts. Normal graphical boot,
application launch/navigation, and idle first-login desktop checks pass. The idle
check confirmed the top panel appears without application launch or panel edits;
software-emulated cold startup needs time to settle. Final BIOS and UEFI ISO boot,
service checks and clean shutdown pass. The VMDK passes qemu-img check and compares
identically to its candidate. Windows copies match the recorded SHA-256 hashes.

Final files and verification logs are in outputs/Aether-Vector. Only x86_64 is
compiled and boot-tested. Existing delivered user disks have not been replaced.
The exported VMX is structurally checked but has not been launched in VMware.
