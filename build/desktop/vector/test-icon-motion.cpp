// SPDX-License-Identifier: GPL-3.0-or-later
#include "icon-motion.h"
#include <QListWidget>
#include <QEventLoop>
#include <QTemporaryDir>
#include <QTimer>
#include <iostream>

static void wait(int milliseconds) {
    QEventLoop loop;
    QTimer::singleShot(milliseconds, &loop, &QEventLoop::quit);
    loop.exec();
}
static QImage frame(QWidget &widget) {
    QImage image(widget.size() * widget.devicePixelRatioF(), QImage::Format_ARGB32_Premultiplied);
    image.setDevicePixelRatio(widget.devicePixelRatioF());
    image.fill(Qt::transparent);
    widget.render(&image);
    return image;
}
int main(int argc, char **argv) {
    QTemporaryDir config;
    qputenv("XDG_CONFIG_HOME", config.path().toUtf8());
    QApplication app(argc, argv);
    QListWidget view;
    view.resize(240, 180);
    view.setIconSize(QSize(56, 56));
    QPixmap icon(56, 56); icon.fill(Qt::red);
    view.addItem(new QListWidgetItem(QIcon(icon), "Test icon"));
    auto *motion = new IconMotion(&view);
    view.setItemDelegate(motion);
    view.show(); wait(50);
    const auto index = view.model()->index(0, 0);
    const auto initial = frame(view);
    motion->pulse(index); wait(70);
    if (frame(view) == initial) { std::cerr << "No animated frame\n"; return 1; }
    wait(300);
    if (frame(view) != initial) { std::cerr << "Icon did not settle\n"; return 1; }
    QSettings settings(config.path() + "/kdeglobals", QSettings::IniFormat);
    settings.setValue("KDE/AnimationDurationFactor", 0); settings.sync();
    motion->pulse(index); wait(70);
    if (frame(view) != initial) { std::cerr << "Reduced motion ignored\n"; return 1; }
    settings.setValue("KDE/AnimationDurationFactor", 1); settings.sync();
    motion->pulse(index); wait(20); motion->pulse(index); view.clear(); wait(300);
    std::cout << "PASS: animated frame, settled frame, reduced motion, repeated click/model reset\n";
}
