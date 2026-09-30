// SPDX-License-Identifier: GPL-2.0-or-later
// Add the menu once without resetting an existing user's panel layout.
var existingPanels = panels();
for (var i = 0; i < existingPanels.length; ++i) {
    var panel = existingPanels[i];
    if (panel.location !== "top") continue;
    var widgets = panel.widgets();
    var found = false;
    for (var j = 0; j < widgets.length; ++j) {
        if (widgets[j].type === "org.aether.powermenu") found = true;
    }
    if (!found) panel.addWidget("org.aether.powermenu");
    break;
}
