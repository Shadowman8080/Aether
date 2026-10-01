#!/usr/bin/env python3
"""Use Aether's three colored controls only with an Aether color scheme."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'kdecoration/breezebutton.cpp';s=p.read_text()
old_scheme = 'return control && general.readEntry("ColorScheme", QString()).startsWith(QStringLiteral("Aether"));'
new_scheme = '''const QString scheme = general.readEntry("ColorScheme", QString());
    return control && (scheme == QStringLiteral("AetherLight") || scheme == QStringLiteral("AetherDark"));'''
if '// Aether window controls' in s:
    if old_scheme in s:
        p.write_text(s.replace(old_scheme, new_scheme))
    else:
        assert new_scheme in s, 'Unexpected existing Aether decoration patch'
    raise SystemExit(0)
s=s.replace('#include <KColorUtils>','#include <KColorUtils>\n#include <KConfigGroup>\n#include <KSharedConfig>')
anchor='using KDecoration3::DecorationButtonType;'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''

// Aether window controls; upstream Breeze behavior remains available with other schemes.
static bool aetherControls(DecorationButtonType type)
{
    const bool control = type == DecorationButtonType::Close
        || type == DecorationButtonType::Minimize || type == DecorationButtonType::Maximize;
    const KConfigGroup general(KSharedConfig::openConfig(QStringLiteral("kdeglobals")), QStringLiteral("General"));
    const QString scheme = general.readEntry("ColorScheme", QString());
    return control && (scheme == QStringLiteral("AetherLight") || scheme == QStringLiteral("AetherDark"));
}
''')
anchor='''QColor Button::foregroundColor() const
{
'''
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''    if (aetherControls(type())) {
        return QColor(32, 34, 40);
    }
''')
anchor='''    auto c = d->window();
    QColor redColor(c->color(ColorGroup::Warning, ColorRole::Foreground));'''
assert s.count(anchor)==1
s=s.replace(anchor,'''    auto c = d->window();
    if (aetherControls(type())) {
        QColor color;
        if (type() == DecorationButtonType::Close) color = QColor(237, 106, 94);
        else if (type() == DecorationButtonType::Minimize) color = QColor(244, 191, 80);
        else color = QColor(98, 197, 84);
        if (!c->isActive()) color = QColor(178, 183, 196);
        if (isPressed()) return color.darker(120);
        if (isHovered()) return color.lighter(108);
        return color;
    }
    QColor redColor(c->color(ColorGroup::Warning, ColorRole::Foreground));''')
p.write_text(s)
print('Applied Aether controls; native actions, glyphs and accessibility names retained.')
