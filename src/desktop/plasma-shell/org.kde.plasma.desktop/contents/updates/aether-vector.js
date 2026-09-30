// SPDX-License-Identifier: GPL-2.0-or-later
// Migrate existing panels without resetting their position, size or other widgets.
var existingPanels = panels();
for (var i = 0; i < existingPanels.length; ++i) {
    var panel = existingPanels[i];
    var widgets = panel.widgets();
    for (var j = 0; j < widgets.length; ++j) {
        var widget = widgets[j];
        if (panel.location === "top" &&
            (widget.type === "org.kde.plasma.kickoff" || widget.type === "org.kde.plasma.kicker" || widget.type === "org.kde.plasma.kickerdash")) {
            widget.remove();
        }
        if (panel.location !== "bottom" ||
            (widget.type !== "org.kde.plasma.icontasks" && widget.type !== "org.kde.plasma.taskmanager")) continue;
        widget.currentConfigGroup = ["General"];
        var launchers = widget.readConfig("launchers", []);
        if (typeof launchers === "string") launchers = launchers ? launchers.split(",") : [];
        var revised = [];
        var hasAura = false;
        for (var k = 0; k < launchers.length; ++k) {
            var launcher = String(launchers[k]);
            if (launcher.indexOf("org.aether.Vector.desktop") !== -1 || launcher.indexOf("org.kde.dolphin.desktop") !== -1) continue;
            revised.push(launcher);
            if (launcher.indexOf("org.aether.AuraSearch.desktop") !== -1) {
                revised.push("applications:org.aether.Vector.desktop");
                hasAura = true;
            }
        }
        if (!hasAura) revised = ["applications:org.aether.AuraSearch.desktop", "applications:org.aether.Vector.desktop"].concat(revised);
        widget.writeConfig("launchers", revised);
        widget.reloadConfig();
    }
}
