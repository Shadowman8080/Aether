// SPDX-License-Identifier: GPL-2.0-or-later
// Runs only when the user applies Aether's desktop layout.
var top = new Panel;
top.location = "top";
top.height = Math.round(gridUnit * 1.7);
top.floating = false;
top.lengthMode = "fill";
top.opacity = "translucent";
var search = top.addWidget("org.kde.plasma.icon");
search.currentConfigGroup = ["General"];
search.writeConfig("url", "file:///usr/share/applications/org.aether.AuraSearch.desktop");
top.addWidget("org.kde.plasma.appmenu");
top.addWidget("org.kde.plasma.panelspacer");
top.addWidget("org.kde.plasma.kimpanel");
top.addWidget("org.kde.plasma.systemtray");
var clock = top.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["General"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateFormat", "shortDate");
top.addWidget("org.aether.powermenu");
var dock = new Panel;
dock.location = "bottom";
dock.height = Math.round(gridUnit * 3.4);
dock.floating = true;
dock.alignment = "center";
dock.lengthMode = "fit";
dock.hiding = "none";
dock.opacity = "adaptive";
var tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", ["applications:org.aether.AuraSearch.desktop", "applications:org.aether.Vector.desktop", "applications:org.aether.Pilot.desktop", "applications:org.kde.konsole.desktop", "applications:systemsettings.desktop"]);
tasks.writeConfig("showOnlyCurrentScreen", true);
dock.addWidget("org.kde.plasma.showdesktop");
var spaces = desktopsForActivity(currentActivity());
for (var i = 0; i < spaces.length; ++i) {
    spaces[i].wallpaperPlugin = "org.kde.image";
    spaces[i].currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    spaces[i].writeConfig("Image", "file:///usr/share/wallpapers/AetherAurora/contents/images/3840x2160.svg");
}
