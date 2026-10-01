// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.private.sessions

PlasmoidItem {
    id: root
    toolTipMainText: i18n("Power")
    toolTipSubText: i18n("Lock, sleep, restart, or shut down")
    preferredRepresentation: fullRepresentation

    SessionManagement { id: session }

    fullRepresentation: PlasmaComponents.ToolButton {
        id: button
        Layout.minimumWidth: 32
        Layout.minimumHeight: 24
        icon.name: "system-shutdown"
        text: i18n("Power")
        display: Controls.AbstractButton.IconOnly
        Accessible.name: i18n("Power menu")
        onPressed: menu.openRelative()

        PlasmaExtras.Menu {
            id: menu
            visualParent: button
            placement: PlasmaExtras.Menu.BottomPosedRightAlignedPopup
            minimumWidth: 210
            PlasmaExtras.MenuItem {
                text: i18n("Lock Computer")
                icon: "system-lock-screen"
                enabled: session.canLock
                onClicked: session.lock()
            }
            PlasmaExtras.MenuItem {
                text: i18n("Sleep")
                icon: "system-suspend"
                enabled: session.canSuspend
                onClicked: session.suspend()
            }
            PlasmaExtras.MenuItem { separator: true }
            PlasmaExtras.MenuItem {
                text: i18n("Restart")
                icon: "system-reboot"
                enabled: session.canReboot
                onClicked: session.requestReboot(SessionManagement.ForcePrompt)
            }
            PlasmaExtras.MenuItem {
                text: i18n("Shut Down")
                icon: "system-shutdown"
                enabled: session.canShutdown
                onClicked: session.requestShutdown(SessionManagement.ForcePrompt)
            }
        }
    }
}
