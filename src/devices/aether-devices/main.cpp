// SPDX-License-Identifier: GPL-3.0-or-later
// Aether Devices — a plug-and-play device manager for Aether Linux.
//
// Aether Devices is the desktop counterpart to the Windows Device Manager:
// it enumerates every device the kernel knows about, groups them by class,
// shows live properties, and refreshes automatically when udev reports a
// hotplug event. Drivers are loaded by the kernel + systemd-udev on hotplug
// (modalias -> modprobe); this application is the human interface to the
// same device tree.
//
// It intentionally uses only udevadm and Qt: no root privileges are needed
// for reading, and there is no extra library dependency beyond Qt6.

#include <QApplication>
#include <QAbstractItemView>
#include <QAction>
#include <QColor>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QHeaderView>
#include <QLabel>
#include <QMainWindow>
#include <QMap>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSplitter>
#include <QStandardPaths>
#include <QStatusBar>
#include <QTableWidget>
#include <QTime>
#include <QTimer>
#include <QToolBar>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QVBoxLayout>
#include <QVariantMap>
#include <QVector>

#include <algorithm>

namespace {

QString udevadm()
{
    const QStringList candidates = {
        QStringLiteral("/usr/bin/udevadm"),
        QStringLiteral("/bin/udevadm"),
        QStandardPaths::findExecutable(QStringLiteral("udevadm")),
    };
    for (const QString &c : candidates)
        if (!c.isEmpty() && QFileInfo::exists(c))
            return c;
    return QStringLiteral("udevadm");
}

bool runCapture(const QStringList &args, QString *output, QString *error)
{
    QProcess p;
    p.start(udevadm(), args);
    if (!p.waitForStarted(5000) || !p.waitForFinished(8000)) {
        if (error)
            *error = p.errorString();
        return false;
    }
    if (output)
        *output = QString::fromLocal8Bit(p.readAllStandardOutput());
    if (error && p.exitCode() != 0)
        *error = QString::fromLocal8Bit(p.readAllStandardError()).trimmed();
    return p.exitCode() == 0;
}

struct Device {
    QString devpath;
    QString subsystem;
    QString devnode;
    QMap<QString, QString> properties;

    QString displayName() const
    {
        QString name = properties.value(QStringLiteral("ID_MODEL"));
        const QString vendor = properties.value(QStringLiteral("ID_VENDOR"));
        if (!name.isEmpty()) {
            if (!vendor.isEmpty())
                name += QStringLiteral(" (") + vendor + QStringLiteral(")");
            return name;
        }
        name = properties.value(QStringLiteral("ID_FS_LABEL"));
        if (!name.isEmpty())
            return name;
        name = properties.value(QStringLiteral("NAME"));
        if (!name.isEmpty())
            return name;
        if (!devnode.isEmpty())
            return devnode;
        const QStringList parts = devpath.split(QLatin1Char('/'));
        return parts.isEmpty() ? devpath : parts.constLast();
    }

    QString driver() const
    {
        QString d = properties.value(QStringLiteral("DRIVER"));
        if (d.isEmpty())
            d = properties.value(QStringLiteral("ID_USB_DRIVER"));
        return d;
    }
};

QString categoryFor(const QString &subsystem)
{
    if (subsystem == QLatin1String("block"))    return QStringLiteral("Storage devices");
    if (subsystem == QLatin1String("net"))      return QStringLiteral("Network adapters");
    if (subsystem == QLatin1String("sound"))    return QStringLiteral("Sound controllers");
    if (subsystem == QLatin1String("input"))    return QStringLiteral("Keyboards, mice and input devices");
    if (subsystem == QLatin1String("video4linux")) return QStringLiteral("Cameras and video capture");
    if (subsystem == QLatin1String("drm"))      return QStringLiteral("Graphics and displays");
    if (subsystem == QLatin1String("usb"))      return QStringLiteral("USB controllers and hubs");
    if (subsystem == QLatin1String("pci"))      return QStringLiteral("PCI devices and buses");
    if (subsystem == QLatin1String("tty"))      return QStringLiteral("Serial ports and modems");
    if (subsystem == QLatin1String("gpio") || subsystem == QLatin1String("i2c") ||
        subsystem == QLatin1String("spi") || subsystem == QLatin1String("pwm") ||
        subsystem == QLatin1String("hwmon") || subsystem == QLatin1String("thermal") ||
        subsystem == QLatin1String("rtc") || subsystem == QLatin1String("leds") ||
        subsystem == QLatin1String("power_supply"))
        return QStringLiteral("On-board and sensor devices");
    return QStringLiteral("Other devices");
}

// Parses `udevadm info -e` ("export"): blocks of P:/M:/R:/U:/D:/N:/L:/S:/E: lines.
QVector<Device> enumerate()
{
    QVector<Device> devices;
    QString out;
    QString err;
    if (!runCapture({QStringLiteral("info"), QStringLiteral("-e")}, &out, &err))
        return devices;

    Device current;
    bool pending = false;
    const QStringList lines = out.split(QLatin1Char('\n'));
    for (const QString &line : lines) {
        if (line.startsWith(QLatin1String("P: "))) {
            if (pending)
                devices.append(current);
            current = Device();
            pending = true;
            current.devpath = line.mid(3).trimmed();
        } else if (line.startsWith(QLatin1String("N: "))) {
            current.devnode = line.mid(3).trimmed();
        } else if (line.startsWith(QLatin1String("U: "))) {
            current.subsystem = line.mid(3).trimmed();
        } else if (line.startsWith(QLatin1String("E: "))) {
            const QString pair = line.mid(3).trimmed();
            const int eq = pair.indexOf(QLatin1Char('='));
            if (eq > 0)
                current.properties.insert(pair.left(eq), pair.mid(eq + 1));
        }
    }
    if (pending)
        devices.append(current);

    // Drop module/"nothing" noise; keep virtual input devices (the seat uses them).
    QVector<Device> visible;
    visible.reserve(devices.size());
    for (const Device &d : devices) {
        if (d.subsystem.isEmpty() || d.subsystem == QLatin1String("module"))
            continue;
        if (d.devpath.startsWith(QLatin1String("/devices/virtual/")) &&
            d.subsystem != QLatin1String("input"))
            continue;
        visible.append(d);
    }
    return visible;
}

} // namespace

class DevicesWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit DevicesWindow(QWidget *parent = nullptr) : QMainWindow(parent)
    {
        setWindowTitle(tr("Aether Devices"));
        resize(960, 620);

        auto *toolbar = addToolBar(tr("Actions"));
        toolbar->setMovable(false);
        toolbar->addAction(tr("Refresh"), this, &DevicesWindow::refreshTree);
        toolbar->addAction(tr("Scan for hardware changes…"), this, &DevicesWindow::rescan);
        toolbar->addAction(tr("Export properties…"), this, &DevicesWindow::exportProperties);

        tree_ = new QTreeWidget(this);
        tree_->setColumnCount(3);
        tree_->setHeaderLabels({tr("Device"), tr("Driver"), tr("Class")});
        tree_->header()->setSectionResizeMode(0, QHeaderView::Stretch);
        tree_->header()->setSectionResizeMode(1, QHeaderView::ResizeToContents);
        tree_->header()->setSectionResizeMode(2, QHeaderView::ResizeToContents);
        tree_->setRootIsDecorated(true);
        tree_->setUniformRowHeights(true);

        props_ = new QTableWidget(0, 2, this);
        props_->setHorizontalHeaderLabels({tr("Property"), tr("Value")});
        props_->horizontalHeader()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
        props_->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
        props_->setEditTriggers(QAbstractItemView::NoEditTriggers);
        props_->verticalHeader()->setVisible(false);

        log_ = new QPlainTextEdit(this);
        log_->setMaximumBlockCount(500);
        log_->setReadOnly(true);
        log_->setVisible(false);

        auto *right = new QWidget(this);
        auto *layout = new QVBoxLayout(right);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->addWidget(props_, 3);
        layout->addWidget(log_, 1);

        auto *split = new QSplitter(Qt::Horizontal, this);
        split->addWidget(tree_);
        split->addWidget(right);
        split->setStretchFactor(0, 3);
        split->setStretchFactor(1, 2);
        setCentralWidget(split);

        auto *showLog = new QAction(tr("Show hotplug log"), this);
        showLog->setCheckable(true);
        showLog->setChecked(false);
        connect(showLog, &QAction::toggled, log_, &QWidget::setVisible);
        toolbar->addAction(showLog);

        status_ = new QLabel(this);
        statusBar()->addWidget(status_);

        connect(tree_, &QTreeWidget::itemSelectionChanged, this, &DevicesWindow::selectionChanged);

        // A burst of hotplug events collapses into one refresh.
        debounce_ = new QTimer(this);
        debounce_->setSingleShot(true);
        debounce_->setInterval(500);
        connect(debounce_, &QTimer::timeout, this, &DevicesWindow::refreshTree);

        monitor_ = new QProcess(this);
        monitor_->setProcessChannelMode(QProcess::MergedChannels);
        connect(monitor_, &QProcess::readyReadStandardOutput, this, &DevicesWindow::monitorOutput);
        startMonitor();

        refreshTree();
    }

    ~DevicesWindow() override
    {
        if (monitor_ && monitor_->state() != QProcess::NotRunning) {
            monitor_->terminate();
            if (!monitor_->waitForFinished(1500))
                monitor_->kill();
        }
    }

private slots:
    void refreshTree()
    {
        const QVector<Device> devices = enumerate();
        tree_->clear();
        QMap<QString, QTreeWidgetItem *> categories;
        for (const Device &d : devices) {
            const QString category = categoryFor(d.subsystem);
            QTreeWidgetItem *cat = categories.value(category);
            if (!cat) {
                cat = new QTreeWidgetItem(tree_);
                cat->setText(0, category);
                cat->setFlags(cat->flags() & ~Qt::ItemIsSelectable);
                categories.insert(category, cat);
            }
            auto *item = new QTreeWidgetItem(cat);
            item->setText(0, d.displayName());
            item->setText(1, d.driver().isEmpty() ? tr("—") : d.driver());
            item->setText(2, d.subsystem);
            item->setData(0, Qt::UserRole, d.devpath);
            QVariantMap props;
            for (auto it = d.properties.cbegin(); it != d.properties.cend(); ++it)
                props.insert(it.key(), it.value());
            item->setData(0, Qt::UserRole + 1, props);
            item->setToolTip(0, d.devpath);
        }
        tree_->expandAll();
        status_->setText(tr("%1 devices detected · udev monitor %2")
                             .arg(devices.size())
                             .arg(monitor_->state() == QProcess::Running ? tr("active") : tr("stopped")));
    }

    void selectionChanged()
    {
        props_->setRowCount(0);
        const auto items = tree_->selectedItems();
        if (items.isEmpty())
            return;
        const QVariantMap props = items.first()->data(0, Qt::UserRole + 1).toMap();
        QStringList keys = props.keys();
        std::sort(keys.begin(), keys.end());
        int row = 0;
        for (const QString &key : keys) {
            props_->insertRow(row);
            auto *k = new QTableWidgetItem(key);
            auto *v = new QTableWidgetItem(props.value(key).toString());
            k->setForeground(QColor(0x40, 0x41, 0x48));
            props_->setItem(row, 0, k);
            props_->setItem(row, 1, v);
            ++row;
        }
    }

    void rescan()
    {
        // The Windows Device Manager "Scan for hardware changes" equivalent.
        const QString helper = QStringLiteral("/usr/libexec/aether-device-rescan");
        if (!QFileInfo::exists(helper)) {
            QMessageBox::information(this, tr("Aether Devices"),
                                     tr("The rescan helper is not installed."));
            return;
        }
        QProcess p;
        p.start(QStringLiteral("pkexec"), {helper});
        if (!p.waitForStarted(3000)) {
            // No polkit in this session; the helper re-execs itself via pkexec.
            QMessageBox::information(this, tr("Aether Devices"),
                                     tr("Launch the rescan helper manually:\npkexec %1").arg(helper));
            return;
        }
        if (!p.waitForFinished(20000)) {
            p.kill();
            QMessageBox::warning(this, tr("Aether Devices"), tr("Rescan timed out."));
            return;
        }
        appendLog(QString::fromLocal8Bit(p.readAllStandardOutput()).trimmed());
        if (p.exitCode() != 0)
            QMessageBox::warning(this, tr("Aether Devices"),
                                 tr("Rescan failed:\n%1")
                                     .arg(QString::fromLocal8Bit(p.readAllStandardError()).trimmed()));
        QTimer::singleShot(600, this, &DevicesWindow::refreshTree);
    }

    void exportProperties()
    {
        const auto items = tree_->selectedItems();
        if (items.isEmpty())
            return;
        const QString devpath = items.first()->data(0, Qt::UserRole).toString();
        const QString file = QFileDialog::getSaveFileName(
            this, tr("Export device properties"), QDir::homePath() + QStringLiteral("/device.txt"),
            tr("Text files (*.txt)"));
        if (file.isEmpty())
            return;
        QString out;
        QString err;
        if (!runCapture({QStringLiteral("info"), QStringLiteral("-q"), QStringLiteral("property"),
                         QStringLiteral("-p"), devpath},
                        &out, &err)) {
            QMessageBox::warning(this, tr("Aether Devices"), tr("Export failed."));
            return;
        }
        QSaveFile f(file);
        if (f.open(QIODevice::WriteOnly)) {
            f.write(out.toUtf8());
            f.commit();
        }
    }

    void monitorOutput()
    {
        monitorBuffer_ += QString::fromLocal8Bit(monitor_->readAllStandardOutput());
        const QStringList blocks =
            monitorBuffer_.split(QRegularExpression(QStringLiteral("\\n{2,}\\s*\\n?")),
                                 Qt::SkipEmptyParts);
        if (blocks.isEmpty())
            return;
        monitorBuffer_ = blocks.constLast();
        for (const QString &block : blocks) {
            const QString action = valueOf(block, QStringLiteral("ACTION"));
            const QString devpath = valueOf(block, QStringLiteral("DEVPATH"));
            const QString subsystem = valueOf(block, QStringLiteral("SUBSYSTEM"));
            if (action.isEmpty() || devpath.isEmpty())
                continue;
            appendLog(QStringLiteral("%1 %2 (%3)").arg(action, devpath, subsystem));
            if (action == QLatin1String("add") || action == QLatin1String("remove"))
                debounce_->start();
        }
    }

    void startMonitor()
    {
        monitor_->start(udevadm(), {QStringLiteral("monitor"), QStringLiteral("--udev"),
                                    QStringLiteral("--property")});
    }

    void appendLog(const QString &line)
    {
        if (line.trimmed().isEmpty())
            return;
        log_->appendPlainText(QStringLiteral("[%1] %2")
                                  .arg(QTime::currentTime().toString(QStringLiteral("HH:mm:ss")),
                                       line));
    }

    static QString valueOf(const QString &block, const QString &key)
    {
        for (const QString &line : block.split(QLatin1Char('\n'))) {
            if (line.startsWith(key + QLatin1Char('=')))
                return line.mid(key.size() + 1);
        }
        return QString();
    }

private:
    QTreeWidget *tree_ = nullptr;
    QTableWidget *props_ = nullptr;
    QPlainTextEdit *log_ = nullptr;
    QLabel *status_ = nullptr;
    QProcess *monitor_ = nullptr;
    QTimer *debounce_ = nullptr;
    QString monitorBuffer_;
};

#include "main.moc"

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("aether-devices"));
    QApplication::setApplicationDisplayName(QStringLiteral("Aether Devices"));
    QApplication::setOrganizationName(QStringLiteral("Aether"));

    DevicesWindow window;
    window.show();
    return app.exec();
}