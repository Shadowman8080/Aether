// SPDX-License-Identifier: GPL-2.0-or-later
// Runs only when the user applies Aether's desktop layout.
var top = new Panel;
top.location = "top";
top.height = Math.round(gridUnit * 1.8);
top.floating = false;
top.lengthMode = "fill";
top.addWidget("org.kde.plasma.appmenu");
top.addWidget("org.kde.plasma.panelspacer");
var search = top.addWidget("org.kde.plasma.icon");
search.currentConfigGroup = ["General"];
search.writeConfig("url", "file:///usr/share/applications/org.aether.AuraSearch.desktop");
top.addWidget("org.kde.plasma.kimpanel");
top.addWidget("org.kde.plasma.systemtray");
top.addWidget("org.kde.plasma.digitalclock");
top.addWidget("org.aether.powermenu");
var dock = new Panel;
dock.location = "bottom";
dock.height = Math.round(gridUnit * 3.2);
dock.floating = true;
dock.alignment = "center";
dock.lengthMode = "fit";
dock.hiding = "dodgewindows";
var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", ["applications:org.aether.AuraSearch.desktop", "applications:org.aether.Vector.desktop", "applications:org.kde.konsole.desktop", "applications:systemsettings.desktop"]);
dock.addWidget("org.kde.plasma.showdesktop");
var spaces = desktopsForActivity(currentActivity());
for (var i = 0; i < spaces.length; ++i) {
    spaces[i].wallpaperPlugin = "org.kde.image";
    spaces[i].currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    spaces[i].writeConfig("Image", "file:///usr/share/wallpapers/AetherAurora/contents/images/3840x2160.svg");
}
