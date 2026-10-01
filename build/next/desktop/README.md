# Aether desktop integration

Plasma 6 global theme and first-login defaults. Layout uses the upstream application menu, system tray, clock and icon task manager. Applications without global-menu support keep their own menus.

Install `etc/` and `usr/` into a package staging root, then package them as `aether-desktop-settings`. The layout must be visually tested in Aether's native Plasma session before release. Do not apply the layout to the Ubuntu build host.

The SVG wallpaper is original Aether artwork, offered under CC0-1.0. Theme configuration and layout script are offered under MIT. KDE Breeze and widgets retain their upstream licenses.

Reference: https://develop.kde.org/docs/plasma/scripting/api/
