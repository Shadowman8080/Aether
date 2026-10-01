// Applied by Plasma when selecting Aether's desktop layout.
// Uses upstream Plasma widgets; no third-party dock dependency.
const top = new Panel;
top.location = "top";
top.height = 32;
top.lengthMode = "fill";
top.floating = false;
const launcher = top.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "aether-assistant");
top.addWidget("org.kde.plasma.appmenu");
top.addWidget("org.kde.plasma.panelspacer");
top.addWidget("org.kde.plasma.systemtray");
const clock = top.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", false);

const dock = new Panel;
dock.location = "bottom";
dock.alignment = "center";
dock.height = 60;
dock.lengthMode = "fit";
dock.hiding = "dodgewindows";
dock.floating = true;
const tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop",
    "applications:org.aether.Assistant.desktop"
]);

desktops().forEach(function(desktop) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/Aether/contents/images/aether.svg");
});
