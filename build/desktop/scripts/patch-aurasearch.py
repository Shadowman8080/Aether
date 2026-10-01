#!/usr/bin/env python3
"""Apply the small Aether UI patch to the pinned Plasma workspace source."""
from pathlib import Path
import sys
src=Path(sys.argv[1])
def replace(name,old,new):
 p=src/name;s=p.read_text()
 if new in s: return
 if s.count(old)!=1: raise SystemExit('Upstream changed; review patch: '+name)
 p.write_text(s.replace(old,new))
replace('krunner/main.cpp','i18n("KRunner"), QStringLiteral(PROJECT_VERSION), i18n("Run Command interface")','i18n("AuraSearch"), QStringLiteral(PROJECT_VERSION), i18n("Aether desktop search, powered by KDE KRunner")')
replace('krunner/view.cpp','setTitle(i18n("KRunner"));','setTitle(i18n("AuraSearch"));')
replace('krunner/qml/RunCommand.qml',': i18nc("Textfield placeholder text", "Search…")',': i18nc("Textfield placeholder text", "AuraSearch — apps, files, settings…")')
replace('krunner/org.kde.krunner.desktop.cmake','X-KDE-Shortcuts=Alt+Space,Alt+F2,Search','X-KDE-Shortcuts=Meta+Space,Alt+Space,Alt+F2,Search')
print('Applied AuraSearch branding and Super+Space shortcut; upstream attribution retained.')
