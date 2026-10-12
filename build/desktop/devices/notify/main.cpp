// SPDX-License-Identifier: GPL-3.0-or-later
// Aether device notifier — the "plug and play" toast.
//
// Runs quietly in the graphical session and watches udev. When hardware is
// plugged in or removed it posts a desktop notification through the
// org.freedesktop.Notifications bus (the same channel Plasma uses), so Aether
// greets new devices the way the Windows tray does.
//
// Rule of hand: only physical, user-visible bus events are announced. Kernel
// virtual devices and bus-internal interface events are suppressed so the
// toast stays useful.

#include <QCoreApplication>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDebug>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QProcess>
#include <QSet>
#include <QStringList>

#include <memory>

namespace {

QString udevadm()
{
    const QStringList candidates = {
        QStringLiteral("/usr/bin/udevadm"),
        QStringLiteral("/bin/udevadm"),
        QStringLiteral("udevadm"),
    };
    for (const QString &c : candidates) {
        if (!c.contains(QLatin1Char('/')) || QFileInfo::exists(c))
            return c;
    }
    return QStringLiteral("udevadm");
}

const QSet<QString> &interestingSubsystems()
{
    static const QSet<QString> set = {
        QStringLiteral("block"),       QStringLiteral("net"),
        QStringLiteral("usb"),         QStringLiteral("sound"),
        QStringLiteral("video4linux"), QStringLiteral("drm"),
        QStringLiteral("tty"),         QStringLiteral("input"),
    };
    return set;
}

QString value(const QString &block, const QString &key)
{
    for (const QString &line : block.split(QLatin1Char('\n'))) {
        if (line.startsWith(key + QLatin1Char('=')))
            return line.mid(key.size() + 1);
    }
    return QString();
}

struct Monitor {
    QProcess process;
    QString buffer;

    void start()
    {
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start(udevadm(), {QStringLiteral("monitor"), QStringLiteral("--udev"),
                                  QStringLiteral("--property")});
    }

    // udevadm monitor --property prints one event per blank-line-terminated block.
    QStringList events()
    {
        buffer += QString::fromLocal8Bit(process.readAllStandardOutput());
        QStringList blocks;
        int split;
        while ((split = buffer.indexOf(QStringLiteral("\n\n"))) >= 0) {
            blocks.append(buffer.left(split));
            buffer.remove(0, split + 2);
        }
        if (buffer.size() > (1 << 20)) // defensive cap
            buffer.clear();
        return blocks;
    }
};

QString describe(const QString &devpath)
{
    QProcess p;
    p.start(udevadm(), {QStringLiteral("info"), QStringLiteral("-q"), QStringLiteral("property"),
                        QStringLiteral("-p"), devpath});
    if (!p.waitForStarted(2000) || !p.waitForFinished(3000))
        return QString();
    const QString out = QString::fromLocal8Bit(p.readAllStandardOutput());
    QString model, vendor;
    for (const QString &line : out.split(QLatin1Char('\n'))) {
        if (line.startsWith(QStringLiteral("ID_MODEL=")))
            model = line.mid(9);
        else if (line.startsWith(QStringLiteral("ID_VENDOR=")))
            vendor = line.mid(10);
    }
    if (!model.isEmpty())
        return vendor.isEmpty() ? model : vendor + QStringLiteral(" ") + model;
    return vendor;
}

void notify(const QString &summary, const QString &body)
{
    QDBusInterface bus(QStringLiteral("org.freedesktop.Notifications"),
                       QStringLiteral("/org/freedesktop/Notifications"),
                       QStringLiteral("org.freedesktop.Notifications"));
    bus.call(QStringLiteral("Notify"),
             QStringLiteral("Aether Devices"),
             0u,
             QStringLiteral("computer"),
             summary,
             body,
             QStringList(),
             QVariantMap(),
             4000);
}

} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("aether-device-notify"));

    Monitor monitor;
    const QString tool = udevadm();
    if (!QFileInfo::exists(tool)) {
        // No udev monitor available: stay silent rather than fail the session.
        qWarning() << "aether-device-notify: udevadm not found:" << tool;
        return 1;
    }
    monitor.start();

    // Simple rate limit: at most one toast per 1500 ms.
    std::unique_ptr<QElapsedTimer> last(new QElapsedTimer);
    last->start();

    QObject::connect(&monitor.process, &QProcess::readyReadStandardOutput, [&]() {
        for (const QString &block : monitor.events()) {
            const QString action = value(block, QStringLiteral("ACTION"));
            const QString devpath = value(block, QStringLiteral("DEVPATH"));
            const QString subsystem = value(block, QStringLiteral("SUBSYSTEM"));
            const QString devtype = value(block, QStringLiteral("DEVTYPE"));
            if (action != QLatin1String("add") && action != QLatin1String("remove"))
                continue;
            if (!interestingSubsystems().contains(subsystem))
                continue;
            if (devpath.startsWith(QLatin1String("/devices/virtual/")) &&
                subsystem != QLatin1String("input"))
                continue;
            if (subsystem == QLatin1String("usb") && devtype == QLatin1String("usb_interface"))
                continue; // the parent usb_device already announced this port
            if (last->elapsed() < 1500)
                continue;

            last->restart();
            QString body = describe(devpath);
            if (body.isEmpty())
                body = devpath.section(QLatin1Char('/'), -1);
            const QString node = value(block, QStringLiteral("DEVNAME"));
            if (!node.isEmpty())
                body += QStringLiteral(" (%1)").arg(node);

            const QString summary = action == QLatin1String("add")
                                        ? QStringLiteral("Device connected")
                                        : QStringLiteral("Device disconnected");
            notify(summary, body);
        }
    });

    const int rc = app.exec();
    monitor.process.terminate();
    return rc;
}