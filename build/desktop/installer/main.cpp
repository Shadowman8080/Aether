// SPDX-License-Identifier: GPL-2.0-or-later
#include <QApplication>
#include <QCheckBox>
#include <QCloseEvent>
#include <QComboBox>
#include <QDialog>
#include <QFile>
#include <QFileDialog>
#include <QFileInfo>
#include <QFontMetrics>
#include <QFormLayout>
#include <QFrame>
#include <QHash>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>
#include <QProcess>
#include <QProgressBar>
#include <QPushButton>
#include <QRegularExpression>
#include <QSet>
#include <QSslCertificate>
#include <QSvgRenderer>
#include <QTextEdit>
#include <QToolButton>
#include <QVBoxLayout>
#include <QWizard>
#include <algorithm>
#include <cmath>

namespace {

constexpr double kPi = 3.14159265358979323846;

struct ZoneInfo {
    QString name;
    double latitude;
    double longitude;
};

QString heading(const QString &text) {
    return QStringLiteral("<span style=\"font-size:25px;font-weight:600;color:#151b2c;\">%1</span>")
        .arg(text.toHtmlEscaped());
}

QString muted(const QString &text) {
    return QStringLiteral("<span style=\"font-size:13px;color:#6b7385;\">%1</span>")
        .arg(text.toHtmlEscaped());
}

bool parseCoordinate(const QString &text, double &latitude, double &longitude) {
    const QString value = text.trimmed();
    int latitudeEnd = -1;
    for (int index = 1; index < value.size(); ++index) {
        if (value.at(index) == QLatin1Char('+') || value.at(index) == QLatin1Char('-')) {
            latitudeEnd = index;
            break;
        }
    }
    if (latitudeEnd > 0) {
        const QString latitudeText = value.mid(1, latitudeEnd - 1);
        const QString longitudeText = value.mid(latitudeEnd + 1);
        if ((latitudeText.size() == 4 || latitudeText.size() == 6) &&
            (longitudeText.size() == 5 || longitudeText.size() == 7)) {
            auto coordinate = [](const QString &digits, int degreeDigits) {
                double result = digits.left(degreeDigits).toDouble();
                result += digits.mid(degreeDigits, 2).toDouble() / 60.0;
                if (digits.size() > degreeDigits + 2) {
                    result += digits.mid(degreeDigits + 2, 2).toDouble() / 3600.0;
                }
                return result;
            };
            latitude = coordinate(latitudeText, 2);
            if (value.at(0) == QLatin1Char('-')) latitude = -latitude;
            longitude = coordinate(longitudeText, 3);
            if (value.at(latitudeEnd) == QLatin1Char('-')) longitude = -longitude;
            return true;
        }
    }
    static const QRegularExpression pattern(
        QStringLiteral("^([+-])(\\d{2})(\\d{2})([+-])(\\d{3})(\\d{2})$"));
    const QRegularExpressionMatch match = pattern.match(text.trimmed());
    if (!match.hasMatch()) return false;
    latitude = match.captured(2).toDouble() + match.captured(3).toDouble() / 60.0;
    if (match.captured(1) == QStringLiteral("-")) latitude = -latitude;
    longitude = match.captured(5).toDouble() + match.captured(6).toDouble() / 60.0;
    if (match.captured(4) == QStringLiteral("-")) longitude = -longitude;
    return true;
}

QVector<ZoneInfo> loadZones() {
    const QStringList tables{QStringLiteral("/usr/share/zoneinfo/zone1970.tab"),
                             QStringLiteral("/usr/share/zoneinfo/zone.tab")};
    QVector<ZoneInfo> zones;
    QSet<QString> seen;
    for (const QString &path : tables) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) continue;
        while (!file.atEnd()) {
            const QString line = QString::fromUtf8(file.readLine()).trimmed();
            if (line.isEmpty() || line.startsWith(QLatin1Char('#'))) continue;
            const QStringList fields = line.split(QLatin1Char('\t'));
            if (fields.size() < 3) continue;
            double latitude = 0.0, longitude = 0.0;
            if (!parseCoordinate(fields.at(1), latitude, longitude)) continue;
            const QString name = fields.at(2).trimmed();
            if (name.isEmpty() || seen.contains(name)) continue;
            seen.insert(name);
            zones.append(ZoneInfo{name, latitude, longitude});
        }
    }
    std::sort(zones.begin(), zones.end(), [](const ZoneInfo &a, const ZoneInfo &b) {
        return a.name < b.name;
    });
    return zones;
}

QString detectTimezone() {
    const QString link = QFileInfo(QStringLiteral("/etc/localtime")).symLinkTarget();
    const int marker = link.indexOf(QStringLiteral("/zoneinfo/"));
    if (marker >= 0) return link.mid(marker + 10);
    QProcess process;
    process.start(QStringLiteral("/usr/bin/timedatectl"),
                  {QStringLiteral("show"), QStringLiteral("-p"), QStringLiteral("Timezone"),
                   QStringLiteral("--value")});
    if (process.waitForFinished(2000) && process.exitCode() == 0) {
        const QString zone = QString::fromUtf8(process.readAllStandardOutput()).trimmed();
        if (!zone.isEmpty()) return zone;
    }
    QFile file(QStringLiteral("/etc/timezone"));
    if (file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        const QString zone = QString::fromUtf8(file.readAll()).trimmed();
        if (!zone.isEmpty()) return zone;
    }
    return QStringLiteral("UTC");
}

QString detectKeyboard() {
    QString keymap;
    QFile file(QStringLiteral("/etc/vconsole.conf"));
    if (file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        while (!file.atEnd()) {
            const QString line = QString::fromUtf8(file.readLine()).trimmed();
            if (line.startsWith(QStringLiteral("KEYMAP="))) {
                keymap = line.mid(7).trimmed();
            }
        }
    }
    static const QHash<QString, QString> layouts{
        {QStringLiteral("us"), QStringLiteral("us")},
        {QStringLiteral("uk"), QStringLiteral("gb")},
        {QStringLiteral("de"), QStringLiteral("de")},
        {QStringLiteral("de-latin1"), QStringLiteral("de")},
        {QStringLiteral("fr"), QStringLiteral("fr")},
        {QStringLiteral("es"), QStringLiteral("es")},
        {QStringLiteral("it"), QStringLiteral("it")},
        {QStringLiteral("pt-latin1"), QStringLiteral("pt")},
        {QStringLiteral("br-abnt2"), QStringLiteral("br")},
    };
    if (layouts.contains(keymap)) return layouts.value(keymap);
    QProcess localectl;
    localectl.start(QStringLiteral("/usr/bin/localectl"), {QStringLiteral("status")});
    if (localectl.waitForFinished(2000)) {
        const QString output = QString::fromUtf8(localectl.readAllStandardOutput());
        static const QRegularExpression pattern(QStringLiteral("X11 Layout:\\s*([a-zA-Z0-9,_-]+)"));
        const QRegularExpressionMatch match = pattern.match(output);
        if (match.hasMatch()) {
            const QString layout = match.captured(1).split(QLatin1Char(',')).first();
            if (layouts.contains(layout)) return layouts.value(layout);
            return layout;
        }
    }
    return QStringLiteral("us");
}

QStringList backupCandidates() {
    QStringList result;
    QFile file(QStringLiteral("/proc/mounts"));
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) return result;
    while (!file.atEnd()) {
        const QString line = QString::fromUtf8(file.readLine()).trimmed();
        const QStringList fields = line.split(QLatin1Char(' '));
        if (fields.size() < 4) continue;
        QString path = fields.at(1);
        path.replace(QStringLiteral("\\040"), QStringLiteral(" "));
        path.replace(QStringLiteral("\\011"), QStringLiteral("\t"));
        path.replace(QStringLiteral("\\134"), QStringLiteral("\\"));
        if (!path.startsWith(QStringLiteral("/mnt/")) &&
            !path.startsWith(QStringLiteral("/media/")) &&
            !path.startsWith(QStringLiteral("/run/media/"))) {
            continue;
        }
        if (path.startsWith(QStringLiteral("/mnt/aether-install"))) continue;
        if (fields.at(3).split(QLatin1Char(',')).contains(QStringLiteral("ro"))) continue;
        if (!QFileInfo(path).isWritable()) continue;
        if (!result.contains(path)) result.append(path);
    }
    return result;
}

bool secureBootEnabled() {
    QFile file(QStringLiteral(
        "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"));
    if (!file.open(QIODevice::ReadOnly)) return false;
    const QByteArray data = file.read(5);
    return data.size() == 5 && data.at(4) == 1;
}

bool secureBootSetupMode() {
    QFile file(QStringLiteral(
        "/sys/firmware/efi/efivars/SetupMode-8be4df61-93ca-11d2-aa0d-00e098032b8c"));
    if (!file.open(QIODevice::ReadOnly)) return false;
    const QByteArray data = file.read(5);
    return data.size() == 5 && data.at(4) == 1;
}

bool aetherKeyEnrolled() {
    QFile certificateFile(QStringLiteral("/usr/share/aether/secureboot/db.crt"));
    if (!certificateFile.open(QIODevice::ReadOnly)) return false;
    const QSslCertificate certificate(&certificateFile, QSsl::Pem);
    const QByteArray der = certificate.toDer();
    if (der.isEmpty()) return false;
    QFile dbFile(QStringLiteral(
        "/sys/firmware/efi/efivars/db-8be4df61-93ca-11d2-aa0d-00e098032b8c"));
    if (!dbFile.open(QIODevice::ReadOnly)) return false;
    return dbFile.readAll().contains(der);
}

QString secureBootSummary() {
    if (!QFileInfo::exists(QStringLiteral("/sys/firmware/efi/efivars"))) {
        return QStringLiteral("Not applicable (BIOS boot)");
    }
    if (secureBootEnabled()) {
        return aetherKeyEnrolled() ? QStringLiteral("Enabled (Aether signed chain)")
                                   : QStringLiteral("Enabled (Aether key not enrolled)");
    }
    if (secureBootSetupMode()) return QStringLiteral("Setup Mode (enrollment available)");
    return QStringLiteral("Disabled (signed chain installed)");
}

QPixmap renderLogo(int size) {
    QPixmap pixmap(size, size);
    pixmap.fill(Qt::transparent);
    QSvgRenderer renderer(QStringLiteral("/usr/share/icons/hicolor/scalable/apps/aether-logo.svg"));
    QPainter painter(&pixmap);
    if (renderer.isValid()) renderer.render(&painter, QRectF(0, 0, size, size));
    painter.end();
    return pixmap;
}

} // namespace

class TimezoneMap final : public QWidget {
    Q_OBJECT
public:
    explicit TimezoneMap(const QVector<ZoneInfo> &zones, QWidget *parent = nullptr)
        : QWidget(parent), m_zones(zones) {
        setMinimumWidth(420);
        setFixedHeight(280);
        setMouseTracking(true);
        setCursor(Qt::PointingHandCursor);
        m_renderer.load(QStringLiteral(":/aether/world.svg"));
    }

    void setZone(const QString &zone) {
        if (m_zone == zone) return;
        m_zone = zone;
        update();
    }

    QString zone() const { return m_zone; }

signals:
    void zonePicked(const QString &zone);

protected:
    void paintEvent(QPaintEvent *) override {
        QPainter painter(this);
        painter.setRenderHint(QPainter::Antialiasing);
        const QRectF area = mapArea();
        QPainterPath clip;
        clip.addRoundedRect(area, 16, 16);
        painter.save();
        painter.setClipPath(clip);
        painter.fillRect(area, QColor(QStringLiteral("#eef4fc")));
        if (m_renderer.isValid()) m_renderer.render(&painter, area);
        for (const ZoneInfo &zone : m_zones) {
            const QPointF point = project(zone.latitude, zone.longitude, area);
            const bool selected = zone.name == m_zone;
            painter.setPen(Qt::NoPen);
            painter.setBrush(selected ? QColor(QStringLiteral("#5b6cf9"))
                                      : QColor(61, 84, 137, 110));
            const double radius = selected ? 5.0 : 2.1;
            painter.drawEllipse(point, radius, radius);
            if (selected) {
                painter.setBrush(Qt::NoBrush);
                painter.setPen(QPen(Qt::white, 2));
                painter.drawEllipse(point, 8, 8);
            }
        }
        if (!m_zone.isEmpty()) {
            for (const ZoneInfo &zone : m_zones) {
                if (zone.name != m_zone) continue;
                const QPointF point = project(zone.latitude, zone.longitude, area);
                QFont labelFont = font();
                labelFont.setPointSize(9);
                const QFontMetrics metrics(labelFont);
                const int width = metrics.horizontalAdvance(zone.name) + 18;
                QRectF label(point.x() + 12, point.y() - 13, width, 26);
                if (label.right() > area.right()) label.moveLeft(point.x() - width - 12);
                if (label.top() < area.top()) label.moveTop(point.y() + 12);
                painter.setPen(Qt::NoPen);
                painter.setBrush(QColor(QStringLiteral("#5b6cf9")));
                painter.drawRoundedRect(label, 7, 7);
                painter.setFont(labelFont);
                painter.setPen(Qt::white);
                painter.drawText(label, Qt::AlignCenter, zone.name);
                break;
            }
        }
        if (m_hovered >= 0 && m_zones.at(m_hovered).name != m_zone) {
            const ZoneInfo &zone = m_zones.at(m_hovered);
            const QPointF point = project(zone.latitude, zone.longitude, area);
            QFont labelFont = font();
            labelFont.setPointSize(9);
            const QFontMetrics metrics(labelFont);
            const int width = metrics.horizontalAdvance(zone.name) + 18;
            QRectF label(point.x() + 12, point.y() - 13, width, 26);
            if (label.right() > area.right()) label.moveLeft(point.x() - width - 12);
            if (label.top() < area.top()) label.moveTop(point.y() + 12);
            painter.setPen(Qt::NoPen);
            painter.setBrush(QColor(23, 33, 61, 235));
            painter.drawRoundedRect(label, 7, 7);
            painter.setFont(labelFont);
            painter.setPen(Qt::white);
            painter.drawText(label, Qt::AlignCenter, zone.name);
        }
        painter.restore();
        painter.setPen(QPen(QColor(179, 196, 227), 1));
        painter.setBrush(Qt::NoBrush);
        painter.drawRoundedRect(area.adjusted(0.5, 0.5, -0.5, -0.5), 16, 16);
    }

    void mousePressEvent(QMouseEvent *event) override {
        if (event->button() != Qt::LeftButton) return;
        const int index = nearest(event->position());
        if (index < 0) return;
        m_zone = m_zones.at(index).name;
        emit zonePicked(m_zone);
        update();
    }

    void mouseMoveEvent(QMouseEvent *event) override {
        const int index = nearest(event->position());
        if (index == m_hovered) return;
        m_hovered = index;
        setToolTip(index >= 0 ? m_zones.at(index).name : QString());
        update();
    }

    void leaveEvent(QEvent *) override {
        m_hovered = -1;
        update();
    }

private:
    QRectF mapArea() const { return QRectF(rect()).adjusted(8, 8, -8, -8); }

    QPointF project(double latitude, double longitude, const QRectF &area) const {
        return QPointF(area.left() + (longitude + 180.0) / 360.0 * area.width(),
                       area.top() + (90.0 - latitude) / 180.0 * area.height());
    }

    int nearest(const QPointF &position) const {
        const QRectF area = mapArea();
        if (!area.contains(position)) return -1;
        const double longitude = (position.x() - area.left()) / area.width() * 360.0 - 180.0;
        const double latitude = 90.0 - (position.y() - area.top()) / area.height() * 180.0;
        const double cosine = std::cos(latitude * kPi / 180.0);
        int best = -1;
        double bestDistance = 1e9;
        for (int index = 0; index < m_zones.size(); ++index) {
            const ZoneInfo &zone = m_zones.at(index);
            const double latitudeDelta = zone.latitude - latitude;
            double longitudeDelta = std::fmod(std::abs(zone.longitude - longitude), 360.0);
            if (longitudeDelta > 180.0) longitudeDelta = 360.0 - longitudeDelta;
            const double distance = latitudeDelta * latitudeDelta +
                                    longitudeDelta * longitudeDelta * cosine * cosine;
            if (distance < bestDistance) {
                bestDistance = distance;
                best = index;
            }
        }
        return best;
    }

    QSvgRenderer m_renderer;
    QVector<ZoneInfo> m_zones;
    QString m_zone;
    int m_hovered = -1;
};

class Installer final : public QWizard {
    Q_OBJECT
public:
    Installer() {
        setWindowTitle(tr("Install Aether Linux"));
        resize(1080, 700);
        setWizardStyle(QWizard::ModernStyle);
        setOption(QWizard::NoBackButtonOnStartPage);
        setOption(QWizard::NoBackButtonOnLastPage);
        setOption(QWizard::NoCancelButtonOnLastPage);
        setButtonText(QWizard::FinishButton, tr("Close"));
        setTitleFormat(Qt::RichText);
        setSubTitleFormat(Qt::RichText);
        setStyleSheet(QStringLiteral(R"(
            QWizard { background: #f5f7fc; }
            QWizardPage { background: transparent; }
            QWizard QLabel { color: #1a2133; font-size: 13px; }
            QLabel#hint { color: #737c91; font-size: 12px; }
            QLabel#tagline { color: #5b6478; font-size: 15px; }
            QLabel#cardTitle { font-size: 14px; font-weight: 600; color: #1a2133; }
            QLabel#summary { font-size: 13px; }
            QLabel#warning { color: #8a3b12; background: #fff1e6; border: 1px solid #f2c9a8;
                             border-radius: 8px; padding: 10px; font-size: 12px; }
            QLabel#zoneLabel { color: #4b566f; font-size: 13px; font-weight: 500; }
            QFrame#card { background: #ffffff; border: 1px solid #e0e5f0; border-radius: 12px; }
            QLineEdit, QComboBox {
                background: #ffffff; color: #1a2133; padding: 8px 10px;
                border: 1px solid #d5dbe9; border-radius: 8px; min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #5b6cf9; padding: 7px 9px; }
            QLineEdit:disabled, QComboBox:disabled { background: #f3f4f8; color: #9aa1b5;
                                                      border-color: #e3e6ef; }
            QComboBox::drop-down { border: none; width: 24px; }
            QToolButton#reveal:disabled { color: #b9bfd1; }
            QCheckBox:disabled { color: #9aa1b5; }
            QListWidget { background: #ffffff; border: 1px solid #d5dbe9; border-radius: 10px;
                          padding: 4px; }
            QListWidget::item { padding: 5px 6px; border-radius: 6px; }
            QListWidget::item:selected { background: #e7eaff; color: #1a2133; }
            QPushButton {
                background: #edf0f8; border: 1px solid #d8ddec; border-radius: 9px;
                padding: 9px 20px; color: #232b3f; font-weight: 500;
            }
            QPushButton:hover { background: #e3e8f5; }
            QPushButton:default { background: #5b6cf9; border-color: #5b6cf9; color: #ffffff; }
            QPushButton:default:hover { background: #4c5de8; }
            QPushButton:disabled { color: #9aa1b5; background: #f0f2f7; border-color: #e3e6ef; }
            QToolButton#reveal { border: none; color: #5b6cf9; font-weight: 600; padding: 0 6px; }
            QToolButton#reveal:hover { color: #3f51d6; }
            QCheckBox { spacing: 8px; }
            QProgressBar { border: 1px solid #d5dbe9; border-radius: 7px; background: #ffffff;
                           min-height: 14px; text-align: center; }
            QProgressBar::chunk { background: #5b6cf9; border-radius: 6px; }
            QTextEdit { background: #ffffff; border: 1px solid #d5dbe9; border-radius: 10px;
                        color: #4a5368; font-family: "DejaVu Sans Mono", monospace; font-size: 11px; }
        )"));

        zones = loadZones();

        const QString detectedZone = detectTimezone();
        bool zonePresent = false;
        for (const ZoneInfo &zone : zones) {
            if (zone.name == detectedZone) {
                zonePresent = true;
                break;
            }
        }
        if (!zonePresent && !detectedZone.isEmpty()) {
            zones.append(ZoneInfo{detectedZone, 0.0, 0.0});
            std::sort(zones.begin(), zones.end(), [](const ZoneInfo &a, const ZoneInfo &b) {
                return a.name < b.name;
            });
        }

        auto *welcomePage = makePage(welcomeId, tr("Welcome"), tr("Install Aether on this computer."));
        auto *welcomeLayout = new QVBoxLayout(welcomePage);
        welcomeLayout->setContentsMargins(12, 8, 12, 8);
        welcomeLayout->setSpacing(16);
        auto *hero = new QHBoxLayout;
        hero->setSpacing(22);
        auto *logo = new QLabel;
        logo->setPixmap(renderLogo(104));
        logo->setFixedSize(104, 104);
        hero->addWidget(logo, 0, Qt::AlignTop);
        auto *intro = new QVBoxLayout;
        intro->setSpacing(6);
        auto *name = new QLabel(QStringLiteral(
            "<span style=\"font-size:28px;font-weight:600;color:#151b2c\">Aether Linux 0.3</span>"));
        auto *tagline = new QLabel(tr("A calm, modern desktop that stays out of your way."));
        tagline->setObjectName(QStringLiteral("tagline"));
        auto *body = new QLabel(tr(
            "We will set up your region, choose a disk, and create your account.\n\n"
            "Only the disk you select is erased. Nothing changes until you confirm at the end."));
        body->setWordWrap(true);
        intro->addWidget(name);
        intro->addWidget(tagline);
        intro->addSpacing(10);
        intro->addWidget(body);
        intro->addStretch();
        hero->addLayout(intro, 1);
        welcomeLayout->addLayout(hero);
        auto *liveNote = new QLabel(tr("This live session keeps no changes after shutdown."));
        liveNote->setObjectName(QStringLiteral("hint"));
        welcomeLayout->addWidget(liveNote);
        welcomeLayout->addStretch();

        auto *regionPage = makePage(regionId, tr("Where are you?"),
                                    tr("Aether detected your time zone and keyboard. Adjust them if needed."));
        auto *regionLayout = new QHBoxLayout(regionPage);
        regionLayout->setContentsMargins(10, 6, 10, 6);
        regionLayout->setSpacing(24);
        auto *mapColumn = new QVBoxLayout;
        mapColumn->setSpacing(10);
        zoneMap = new TimezoneMap(zones);
        mapColumn->addWidget(zoneMap, 0);
        zoneLabel = new QLabel;
        zoneLabel->setObjectName(QStringLiteral("zoneLabel"));
        zoneLabel->setMinimumHeight(22);
        mapColumn->addWidget(zoneLabel);
        mapColumn->addStretch();
        regionLayout->addLayout(mapColumn, 3);
        auto *sideColumn = new QVBoxLayout;
        sideColumn->setSpacing(10);
        zoneSearch = new QLineEdit;
        zoneSearch->setPlaceholderText(tr("Search time zones"));
        zoneSearch->setClearButtonEnabled(true);
        sideColumn->addWidget(zoneSearch);
        zoneList = new QListWidget;
        zoneList->setAlternatingRowColors(false);
        zoneList->setUniformItemSizes(true);
        for (const ZoneInfo &zone : zones) {
            auto *item = new QListWidgetItem(zone.name);
            item->setData(Qt::UserRole, zone.name);
            zoneList->addItem(item);
        }
        sideColumn->addWidget(zoneList, 1);
        auto *keyboardForm = new QFormLayout;
        keyboardForm->setContentsMargins(0, 4, 0, 0);
        keyboard = new QComboBox;
        keyboard->addItem(tr("English (US)"), QStringLiteral("us"));
        keyboard->addItem(tr("English (UK)"), QStringLiteral("gb"));
        keyboard->addItem(tr("German"), QStringLiteral("de"));
        keyboard->addItem(tr("French"), QStringLiteral("fr"));
        keyboard->addItem(tr("Spanish"), QStringLiteral("es"));
        keyboard->addItem(tr("Italian"), QStringLiteral("it"));
        keyboard->addItem(tr("Portuguese"), QStringLiteral("pt"));
        keyboard->addItem(tr("Portuguese (Brazil)"), QStringLiteral("br"));
        keyboardForm->addRow(tr("Keyboard layout"), keyboard);
        sideColumn->addLayout(keyboardForm);
        regionLayout->addLayout(sideColumn, 2);

        connect(zoneSearch, &QLineEdit::textChanged, this, [this](const QString &text) {
            for (int index = 0; index < zoneList->count(); ++index) {
                QListWidgetItem *item = zoneList->item(index);
                item->setHidden(!item->text().contains(text, Qt::CaseInsensitive));
            }
        });
        connect(zoneList, &QListWidget::currentItemChanged, this,
                [this](QListWidgetItem *current, QListWidgetItem *) {
                    if (!current || syncingZone) return;
                    selectZone(current->data(Qt::UserRole).toString(), true);
                });
        connect(zoneMap, &TimezoneMap::zonePicked, this, [this](const QString &zone) {
            selectZone(zone, true);
        });

        selectZone(detectedZone);

        const QString detectedKeyboard = detectKeyboard();
        const int keyboardIndex = keyboard->findData(detectedKeyboard);
        if (keyboardIndex >= 0) keyboard->setCurrentIndex(keyboardIndex);

        auto *diskPage = makePage(diskId, tr("Choose a disk"),
                                  tr("Only unmounted writable whole disks of at least 16 GiB are listed."));
        auto *diskLayout = new QVBoxLayout(diskPage);
        diskLayout->setContentsMargins(10, 6, 10, 6);
        diskLayout->setSpacing(14);
        disks = new QComboBox;
        disks->setAccessibleName(tr("Installation disk"));
        diskLayout->addWidget(disks);
        auto *refresh = new QPushButton(tr("Refresh disks"));
        auto *refreshRow = new QHBoxLayout;
        refreshRow->addWidget(refresh);
        refreshRow->addStretch();
        diskLayout->addLayout(refreshRow);
        connect(refresh, &QPushButton::clicked, this, [this] { refreshDisks(); });
        auto *plan = new QFrame;
        plan->setObjectName(QStringLiteral("card"));
        auto *planLayout = new QVBoxLayout(plan);
        planLayout->setContentsMargins(16, 14, 16, 14);
        planLayout->setSpacing(6);
        auto *planTitle = new QLabel(tr("Automatic partitioning"));
        planTitle->setObjectName(QStringLiteral("cardTitle"));
        auto *planText = new QLabel(tr(
            "Aether creates a 512 MiB EFI system partition and formats the rest of the disk as ext4. "
            "The selected disk is erased and formatted automatically when installation starts. "
            "Other disks are left untouched."));
        planText->setWordWrap(true);
        planLayout->addWidget(planTitle);
        planLayout->addWidget(planText);
        diskLayout->addWidget(plan);
        if (secureBootSetupMode()) {
            auto *enrollCard = new QFrame;
            enrollCard->setObjectName(QStringLiteral("card"));
            auto *enrollLayout = new QVBoxLayout(enrollCard);
            enrollLayout->setContentsMargins(16, 14, 16, 14);
            enrollLayout->setSpacing(8);
            auto *enrollTitle = new QLabel(tr("Secure Boot key enrollment"));
            enrollTitle->setObjectName(QStringLiteral("cardTitle"));
            auto *enrollText = new QLabel(tr(
                "Firmware is in Setup Mode. Enroll Aether's public Secure Boot key now, then reboot "
                "before installing. Aether will install a signed shim, GRUB and kernel."));
            enrollText->setWordWrap(true);
            auto *enroll = new QPushButton(tr("Enroll Aether Secure Boot key"));
            auto *enrollRow = new QHBoxLayout;
            enrollRow->addWidget(enroll);
            enrollRow->addStretch();
            enrollLayout->addWidget(enrollTitle);
            enrollLayout->addWidget(enrollText);
            enrollLayout->addLayout(enrollRow);
            diskLayout->addWidget(enrollCard);
            connect(enroll, &QPushButton::clicked, this, [this, enroll] {
                QProcess process;
                process.setProcessChannelMode(QProcess::MergedChannels);
                process.start(QStringLiteral("pkexec"),
                              {QStringLiteral("/usr/libexec/aether-secureboot-enroll")});
                if (!process.waitForStarted(15000)) {
                    QMessageBox::warning(this, tr("Secure Boot enrollment"),
                                         tr("Could not start the enrollment helper."));
                    return;
                }
                process.waitForFinished(180000);
                const QString output = QString::fromLocal8Bit(process.readAll()).trimmed();
                if (process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0 &&
                    output.contains(QStringLiteral("AETHER_SECUREBOOT_ENROLLED"))) {
                    enroll->setEnabled(false);
                    QMessageBox::information(this, tr("Secure Boot enrollment"),
                        tr("Aether's key was enrolled. Reboot the computer, keep Secure Boot enabled, "
                           "then start the installer again to use the signed boot chain."));
                } else {
                    QMessageBox::warning(this, tr("Secure Boot enrollment"),
                        output.isEmpty() ? tr("Enrollment did not complete.") : output);
                }
            });
        } else if (secureBootEnabled() && !aetherKeyEnrolled()) {
            auto *warning = new QLabel(tr(
                "Secure Boot is enabled, but Aether's key is not enrolled. Disable Secure Boot "
                "in firmware, or clear the firmware keys and enroll Aether's key, before installing."));
            warning->setObjectName(QStringLiteral("warning"));
            warning->setWordWrap(true);
            diskLayout->addWidget(warning);
        } else if (secureBootEnabled()) {
            auto *ready = new QLabel(tr(
                "Secure Boot is enabled and Aether's signed boot chain is enrolled. "
                "The installed system will be verified by firmware."));
            ready->setObjectName(QStringLiteral("hint"));
            ready->setWordWrap(true);
            diskLayout->addWidget(ready);
        }
        diskLayout->addStretch();

        auto *accountPage = makePage(accountId, tr("Create your account"),
                                     tr("Your password protects this computer. Use at least 12 characters."));
        auto *accountForm = new QFormLayout(accountPage);
        accountForm->setContentsMargins(10, 6, 10, 6);
        accountForm->setSpacing(14);
        accountForm->setLabelAlignment(Qt::AlignLeft | Qt::AlignVCenter);
        username = new QLineEdit(QStringLiteral("aether"));
        username->setMaxLength(31);
        accountForm->addRow(tr("Account name"), username);
        auto *passwordRow = secretPair(password, passwordConfirm, tr("Password"), tr("Confirm"));
        accountForm->addRow(tr("Password"), passwordRow);
        encrypt = new QCheckBox(tr("Encrypt the system with LUKS2"));
        accountForm->addRow(QString(), encrypt);
        lvm = new QCheckBox(tr("Put the encrypted root in an LVM volume group"));
        lvm->setToolTip(tr("Use LVM inside the LUKS container for the root filesystem."));
        accountForm->addRow(QString(), lvm);
        encryptionNote = new QLabel;
        encryptionNote->setObjectName(QStringLiteral("hint"));
        encryptionNote->setWordWrap(true);
        accountForm->addRow(QString(), encryptionNote);
        storageRow = secretPair(storage, storageConfirm, tr("Storage passphrase"),
                                tr("Confirm passphrase"));
        accountForm->addRow(tr("Storage passphrase"), storageRow);
        recoveryRow = secretPair(recovery, recoveryConfirm, tr("Recovery passphrase"),
                                 tr("Confirm passphrase"));
        accountForm->addRow(tr("Recovery passphrase"), recoveryRow);
        QWidget *storageLabel = accountForm->labelForField(storageRow);
        QWidget *recoveryLabel = accountForm->labelForField(recoveryRow);
        savedRecovery = new QCheckBox(tr("I saved the recovery passphrase somewhere safe"));
        accountForm->addRow(QString(), savedRecovery);
        backup = new QComboBox;
        backup->addItem(tr("Set up after installation"), QString());
        for (const QString &path : backupCandidates()) backup->addItem(path, path);
        auto *backupRow = new QWidget;
        auto *backupLayout = new QHBoxLayout(backupRow);
        backupLayout->setContentsMargins(0, 0, 0, 0);
        backupLayout->setSpacing(8);
        backupLayout->addWidget(backup, 1);
        auto *browse = new QPushButton(tr("Browse…"));
        connect(browse, &QPushButton::clicked, this, [this] {
            const QString directory = QFileDialog::getExistingDirectory(
                this, tr("Choose a backup destination"), QStringLiteral("/mnt"));
            if (directory.isEmpty()) return;
            int index = backup->findData(directory);
            if (index < 0) {
                backup->addItem(directory, directory);
                index = backup->count() - 1;
            }
            backup->setCurrentIndex(index);
        });
        backupLayout->addWidget(browse);
        accountForm->addRow(tr("Backup destination"), backupRow);

        const bool cryptoReady =
            QFileInfo(QStringLiteral("/usr/sbin/cryptsetup")).isExecutable() &&
            QFileInfo(QStringLiteral("/usr/lib/aether-initramfs/encrypted-init")).isExecutable() &&
            QFileInfo(QStringLiteral("/usr/bin/aether-mkinitramfs")).isExecutable();
        const bool lvmReady = QFileInfo(QStringLiteral("/usr/sbin/lvm")).isExecutable();
        if (cryptoReady) {
            encryptionNote->setText(lvmReady
                ? tr("Boot files stay unencrypted in /boot. Keep the recovery passphrase somewhere offline. "
                     "LVM can be enabled for the encrypted root.")
                : tr("Boot files stay unencrypted in /boot. Keep the recovery passphrase somewhere offline. "
                     "LVM support is unavailable because lvm2 is not installed."));
        } else {
            encrypt->setEnabled(false);
            encrypt->setToolTip(tr("Encryption is unavailable because cryptsetup is not installed."));
            encryptionNote->setText(tr(
                "Encryption is unavailable in this live image because cryptsetup and the encryption "
                "initramfs are missing. The installed system will use an unencrypted root filesystem."));
        }
        auto updateCrypto = [this, cryptoReady, lvmReady, storageLabel, recoveryLabel](bool checked) {
            const bool use = checked && cryptoReady;
            storageRow->setVisible(use);
            recoveryRow->setVisible(use);
            savedRecovery->setVisible(use);
            lvm->setVisible(use);
            lvm->setEnabled(use && lvmReady);
            if (!use) lvm->setChecked(false);
            if (storageLabel) storageLabel->setVisible(use);
            if (recoveryLabel) recoveryLabel->setVisible(use);
        };
        connect(encrypt, &QCheckBox::toggled, this, updateCrypto);
        updateCrypto(false);

        auto *reviewPage = makePage(reviewId, tr("Ready to install?"),
                                    tr("Review the summary. The selected disk is erased only after you confirm."));
        auto *reviewLayout = new QVBoxLayout(reviewPage);
        reviewLayout->setContentsMargins(10, 4, 10, 6);
        reviewLayout->setSpacing(12);
        review = new QLabel;
        review->setTextFormat(Qt::RichText);
        review->setWordWrap(true);
        review->setObjectName(QStringLiteral("summary"));
        reviewLayout->addWidget(review);
        confirmation = new QLineEdit;
        confirmation->setPlaceholderText(tr("ERASE /dev/sda"));
        reviewLayout->addWidget(confirmation);
        auto *reviewHint = new QLabel(
            tr("Type the exact line shown above. This is the last step before the disk is erased."));
        reviewHint->setObjectName(QStringLiteral("hint"));
        reviewHint->setWordWrap(true);
        reviewLayout->addWidget(reviewHint);
        reviewLayout->addStretch();

        auto *progressPage = makePage(progressId, tr("Installing Aether"),
                                      tr("Keep this window open and the computer powered on."));
        auto *progressLayout = new QVBoxLayout(progressPage);
        progressLayout->setContentsMargins(10, 6, 10, 6);
        progressLayout->setSpacing(12);
        status = new QLabel(tr("Waiting to begin."));
        status->setWordWrap(true);
        progress = new QProgressBar;
        progress->setRange(0, 7);
        progress->setValue(0);
        progress->setTextVisible(false);
        details = new QTextEdit;
        details->setReadOnly(true);
        details->setMinimumHeight(170);
        progressLayout->addWidget(status);
        progressLayout->addWidget(progress);
        progressLayout->addWidget(details, 1);

        connect(&process, &QProcess::readyReadStandardOutput, this, [this] {
            pending += process.readAllStandardOutput();
            int end = -1;
            while ((end = pending.indexOf('\n')) >= 0) {
                const QByteArray line = pending.left(end);
                pending.remove(0, end + 1);
                if (line.startsWith("AETHER_PROGRESS ")) {
                    const QJsonObject entry = QJsonDocument::fromJson(line.mid(16)).object();
                    progress->setValue(entry[QStringLiteral("step")].toInt());
                    status->setText(entry[QStringLiteral("message")].toString());
                } else {
                    details->append(QString::fromUtf8(line).toHtmlEscaped());
                }
            }
        });
        connect(&process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
                [this](int code, QProcess::ExitStatus state) {
                    running = false;
                    progress->setRange(0, 7);
                    if (code == 0 && state == QProcess::NormalExit) {
                        progress->setValue(7);
                        status->setText(tr(
                            "Aether is installed. Shut down, remove the ISO, then start your new system."));
                    } else {
                        status->setText(tr(
                            "Installation did not complete. Review the details below. Do not assume the "
                            "disk is unchanged if installation had started."));
                    }
                    setButtonText(QWizard::FinishButton, tr("Close"));
                    button(QWizard::FinishButton)->setEnabled(true);
                    button(QWizard::CancelButton)->setEnabled(false);
                });

        paintSidebar(welcomeId);
    }

    void setStartPage(const QString &name) {
        if (name == QStringLiteral("region")) setStartId(regionId);
        else if (name == QStringLiteral("disk")) setStartId(diskId);
        else if (name == QStringLiteral("account")) setStartId(accountId);
        else if (name == QStringLiteral("review")) setStartId(reviewId);
        else setStartId(welcomeId);
    }

protected:
    bool validateCurrentPage() override {
        const QString error = problem();
        if (!error.isEmpty()) {
            QMessageBox::warning(this, tr("Check your choices"), error);
            return false;
        }
        return !running;
    }

    void initializePage(int id) override {
        QWizard::initializePage(id);
        if (id == regionId) zoneMap->setZone(selectedZone);
        if (id == diskId) refreshDisks();
        if (id == reviewId) {
            updateReview();
            confirmation->clear();
        }
        setButtonText(QWizard::NextButton,
                      id == reviewId ? tr("Erase disk and install") : tr("Continue"));
        if (id == progressId) install();
        paintSidebar(id);
    }

    void closeEvent(QCloseEvent *event) override {
        if (running) event->ignore();
        else QWizard::closeEvent(event);
    }

    void reject() override {
        if (!running) QWizard::reject();
    }

private:
    QWizardPage *makePage(int &id, const QString &title, const QString &subtitle) {
        auto *page = new QWizardPage;
        page->setTitle(heading(title));
        page->setSubTitle(muted(subtitle));
        id = addPage(page);
        return page;
    }

    QWidget *secretPair(QLineEdit *&first, QLineEdit *&second, const QString &firstHint,
                        const QString &secondHint) {
        auto *row = new QWidget;
        auto *layout = new QHBoxLayout(row);
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(8);
        first = new QLineEdit;
        second = new QLineEdit;
        for (QLineEdit *field : {first, second}) {
            field->setEchoMode(QLineEdit::Password);
            field->setMaxLength(1024);
            field->setInputMethodHints(Qt::ImhSensitiveData | Qt::ImhNoPredictiveText);
        }
        first->setPlaceholderText(firstHint);
        second->setPlaceholderText(secondHint);
        layout->addWidget(first, 1);
        layout->addWidget(second, 1);
        auto *reveal = new QToolButton;
        reveal->setText(QStringLiteral("Show"));
        reveal->setCheckable(true);
        reveal->setCursor(Qt::PointingHandCursor);
        reveal->setObjectName(QStringLiteral("reveal"));
        reveal->setAccessibleName(tr("Show password"));
        connect(reveal, &QToolButton::toggled, this, [first, second, reveal](bool visible) {
            for (QLineEdit *field : {first, second}) {
                field->setEchoMode(visible ? QLineEdit::Normal : QLineEdit::Password);
            }
            reveal->setText(visible ? QStringLiteral("Hide") : QStringLiteral("Show"));
            reveal->setAccessibleName(visible ? QStringLiteral("Hide password")
                                               : QStringLiteral("Show password"));
        });
        layout->addWidget(reveal);
        return row;
    }

    static bool mounted(const QJsonObject &node) {
        for (const auto &point : node[QStringLiteral("mountpoints")].toArray()) {
            if (!point.isNull() && !point.toString().isEmpty()) return true;
        }
        for (const auto &child : node[QStringLiteral("children")].toArray()) {
            if (mounted(child.toObject())) return true;
        }
        return false;
    }

    void refreshDisks() {
        disks->clear();
        QProcess list;
        list.start(QStringLiteral("/usr/bin/lsblk"),
                   {QStringLiteral("-J"), QStringLiteral("-b"), QStringLiteral("-o"),
                    QStringLiteral("PATH,SIZE,MODEL,TYPE,RO,MOUNTPOINTS")});
        if (!list.waitForFinished(5000) || list.exitCode() != 0) {
            disks->addItem(tr("Could not read the disk list. Select Refresh to try again."), QString());
            return;
        }
        const QJsonArray entries = QJsonDocument::fromJson(list.readAllStandardOutput())
                                       .object()[QStringLiteral("blockdevices")]
                                       .toArray();
        for (const auto &entry : entries) {
            const QJsonObject disk = entry.toObject();
            const double size = disk[QStringLiteral("size")].toVariant().toDouble();
            if (disk[QStringLiteral("type")].toString() != QStringLiteral("disk") ||
                disk[QStringLiteral("ro")].toVariant().toBool() || mounted(disk) ||
                size < 16.0 * 1024 * 1024 * 1024) {
                continue;
            }
            const QString path = disk[QStringLiteral("path")].toString();
            disks->addItem(QStringLiteral("%1  ·  %2 GiB  ·  %3")
                               .arg(path)
                               .arg(size / (1024 * 1024 * 1024), 0, 'f', 1)
                               .arg(disk[QStringLiteral("model")].toString().trimmed()),
                           path);
        }
        if (!disks->count()) {
            disks->addItem(tr("No eligible disk. Attach an empty disk of at least 16 GiB."), QString());
        }
    }

    void selectZone(const QString &zone, bool fromUser = false) {
        if (zone.isEmpty()) return;
        selectedZone = zone;
        syncingZone = true;
        const QList<QListWidgetItem *> matches = zoneList->findItems(zone, Qt::MatchExactly);
        if (!matches.isEmpty()) {
            zoneList->setCurrentItem(matches.first());
            zoneList->scrollToItem(matches.first());
        }
        syncingZone = false;
        zoneMap->setZone(zone);
        zoneLabel->setText(fromUser ? tr("Selected time zone: %1").arg(zone)
                                    : tr("Detected time zone: %1").arg(zone));
    }

    QString problem() const {
        if (currentId() == diskId && disks->currentData().toString().isEmpty()) {
            return tr("Select an unmounted, writable disk of at least 16 GiB.");
        }
        if (currentId() == accountId) {
            if (!QRegularExpression(QStringLiteral("^[a-z][a-z0-9_-]{0,30}$"))
                     .match(username->text())
                     .hasMatch()) {
                return tr("Use a lowercase account name, starting with a letter.");
            }
            if (password->text().size() < 12 || password->text() != passwordConfirm->text()) {
                return tr("Enter matching passwords of at least twelve characters.");
            }
            if (encrypt->isChecked()) {
                if (storage->text().size() < 12 || recovery->text().size() < 12) {
                    return tr("Use storage and recovery passphrases of at least twelve characters.");
                }
                if (storage->text() == recovery->text()) {
                    return tr("The storage and recovery passphrases must be different.");
                }
                if (storage->text() != storageConfirm->text() ||
                    recovery->text() != recoveryConfirm->text()) {
                    return tr("The passphrases and their confirmations do not match.");
                }
                if (!savedRecovery->isChecked()) {
                    return tr("Confirm that you saved the recovery passphrase.");
                }
            }
        }
        if (currentId() == reviewId) {
            if (secureBootEnabled() && !aetherKeyEnrolled()) {
                return tr("Secure Boot is enabled without Aether's key. Disable Secure Boot "
                          "or clear the firmware keys and enroll Aether's key before installing.");
            }
            if (confirmation->text() !=
                QStringLiteral("ERASE ") + disks->currentData().toString()) {
                return tr("Type the exact confirmation shown above.");
            }
        }
        return {};
    }

    void updateReview() {
        const QString diskValue = disks->currentData().toString();
        const QString disk = diskValue.isEmpty() ? tr("No disk selected") : diskValue;
        const QString backupChoice = backup->currentData().toString();
        const QString encryptionText =
            encrypt->isChecked()
                ? (lvm->isChecked() ? tr("LUKS2 with LVM (boot files unencrypted)")
                                    : tr("LUKS2 (boot files unencrypted)"))
                : tr("Off");
        const QString backupText =
            backupChoice.isEmpty() ? tr("Set up after installation") : backupChoice;
        review->setText(
            tr("<table cellspacing=\"0\" cellpadding=\"5\" width=\"100%\">"
               "<tr><td style=\"color:#687086\">Disk</td><td><b>%1</b><br>"
               "<span style=\"color:#687086\">Erased and formatted automatically</span></td></tr>"
               "<tr><td style=\"color:#687086\">Time zone</td><td>%2</td></tr>"
               "<tr><td style=\"color:#687086\">Keyboard</td><td>%3</td></tr>"
               "<tr><td style=\"color:#687086\">Account</td><td>%4</td></tr>"
               "<tr><td style=\"color:#687086\">Encryption</td><td>%5</td></tr>"
               "<tr><td style=\"color:#687086\">Backups</td><td>%6</td></tr>"
               "<tr><td style=\"color:#687086\">Secure Boot</td><td>%7</td></tr>"
               "</table>")
                .arg(disk.toHtmlEscaped())
                .arg(selectedZone.toHtmlEscaped())
                .arg(keyboard->currentText().toHtmlEscaped())
                .arg(username->text().toHtmlEscaped())
                .arg(encryptionText)
                .arg(backupText.toHtmlEscaped())
                .arg(secureBootSummary().toHtmlEscaped()));
        confirmation->setPlaceholderText(QStringLiteral("ERASE ") + diskValue);
    }

    void install() {
        if (started) return;
        started = true;
        if (!QFileInfo::exists(QStringLiteral("/run/initramfs/live/lower/etc/os-release"))) {
            status->setText(tr("Boot the Aether live ISO to install. No disk was changed."));
            button(QWizard::FinishButton)->setEnabled(true);
            return;
        }
        const QJsonObject config{
            {QStringLiteral("disk"), disks->currentData().toString()},
            {QStringLiteral("username"), username->text()},
            {QStringLiteral("password"), password->text()},
            {QStringLiteral("encrypt"), encrypt->isChecked()},
            {QStringLiteral("lvm"), encrypt->isChecked() && lvm->isChecked()},
            {QStringLiteral("storage_password"), storage->text()},
            {QStringLiteral("recovery_password"), recovery->text()},
            {QStringLiteral("backup"), backup->currentData().toString()},
            {QStringLiteral("timezone"), selectedZone},
            {QStringLiteral("keyboard"), keyboard->currentData().toString()},
            {QStringLiteral("language"), QStringLiteral("en_US.UTF-8")},
            {QStringLiteral("confirmation"),
             QStringLiteral("ERASE ") + disks->currentData().toString()},
        };
        running = true;
        button(QWizard::BackButton)->setEnabled(false);
        button(QWizard::CancelButton)->setEnabled(false);
        button(QWizard::FinishButton)->setEnabled(false);
        progress->setRange(0, 0);
        status->setText(tr("Authorizing installation to begin…"));
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start(QStringLiteral("/usr/bin/pkexec"),
                      {QStringLiteral("/usr/libexec/aether-installer-backend"),
                       QStringLiteral("--graphical")});
        if (!process.waitForStarted(5000)) {
            running = false;
            status->setText(tr("The installation service could not start. No disk was changed."));
            button(QWizard::FinishButton)->setEnabled(true);
            return;
        }
        process.write(QJsonDocument(config).toJson(QJsonDocument::Compact));
        process.closeWriteChannel();
        password->clear();
        passwordConfirm->clear();
        storage->clear();
        storageConfirm->clear();
        recovery->clear();
        recoveryConfirm->clear();
    }

    void paintSidebar(int current) {
        QPixmap pixmap(214, 700);
        pixmap.fill(QColor(QStringLiteral("#111a2e")));
        QPainter painter(&pixmap);
        painter.setRenderHint(QPainter::Antialiasing);
        QLinearGradient gradient(0, 0, 214, 700);
        gradient.setColorAt(0.0, QColor(QStringLiteral("#16223c")));
        gradient.setColorAt(1.0, QColor(QStringLiteral("#0c1425")));
        painter.fillRect(pixmap.rect(), gradient);
        QSvgRenderer logo(QStringLiteral("/usr/share/icons/hicolor/scalable/apps/aether-logo.svg"));
        if (logo.isValid()) logo.render(&painter, QRectF(28, 34, 58, 58));
        QFont font = painter.font();
        font.setPointSize(15);
        font.setBold(true);
        painter.setFont(font);
        painter.setPen(Qt::white);
        painter.drawText(QRect(28, 104, 170, 28), QStringLiteral("Aether"));
        font.setPointSize(9);
        font.setBold(false);
        painter.setFont(font);
        painter.setPen(QColor(QStringLiteral("#91a1c4")));
        painter.drawText(QRect(28, 132, 170, 20), QStringLiteral("Linux 0.3"));

        struct Step { int id; const char *label; };
        const Step steps[] = {{regionId, "Region"}, {diskId, "Disk"},
                              {accountId, "Account"}, {reviewId, "Review"}};
        int y = 224;
        for (int index = 0; index < 4; ++index) {
            const bool active = current == steps[index].id;
            const bool done = current > steps[index].id;
            painter.setPen(Qt::NoPen);
            painter.setBrush(active ? QColor(QStringLiteral("#5b6cf9"))
                                    : done ? QColor(QStringLiteral("#33456f"))
                                           : QColor(QStringLiteral("#212e4b")));
            painter.drawEllipse(QPointF(43, y + 13), 13, 13);
            font.setPointSize(9);
            font.setBold(true);
            painter.setFont(font);
            painter.setPen(active ? Qt::white : QColor(QStringLiteral("#aebbd8")));
            painter.drawText(QRect(30, y + 1, 26, 26), Qt::AlignCenter,
                             QString::number(index + 1));
            font.setPointSize(11);
            font.setBold(active);
            painter.setFont(font);
            painter.setPen(active ? Qt::white : QColor(QStringLiteral("#98a7c8")));
            painter.drawText(QRect(70, y + 3, 130, 26), Qt::AlignVCenter, steps[index].label);
            y += 58;
        }
        painter.setPen(QColor(QStringLiteral("#223052")));
        painter.drawLine(28, 656, 186, 656);
        font.setPointSize(8);
        font.setBold(false);
        painter.setFont(font);
        painter.setPen(QColor(QStringLiteral("#7787a8")));
        painter.drawText(QRect(28, 668, 170, 20), QStringLiteral("aetherlinux.org"));
        setPixmap(QWizard::WatermarkPixmap, pixmap);
    }

    int welcomeId = -1, regionId = -1, diskId = -1, accountId = -1;
    int reviewId = -1, progressId = -1;
    QVector<ZoneInfo> zones;
    TimezoneMap *zoneMap = nullptr;
    QListWidget *zoneList = nullptr;
    QLineEdit *zoneSearch = nullptr;
    QLabel *zoneLabel = nullptr;
    QString selectedZone;
    bool syncingZone = false;
    QComboBox *keyboard = nullptr;
    QComboBox *disks = nullptr;
    QLineEdit *username = nullptr, *password = nullptr, *passwordConfirm = nullptr;
    QLineEdit *storage = nullptr, *storageConfirm = nullptr;
    QLineEdit *recovery = nullptr, *recoveryConfirm = nullptr;
    QCheckBox *encrypt = nullptr, *lvm = nullptr, *savedRecovery = nullptr;
    QLabel *encryptionNote = nullptr;
    QWidget *storageRow = nullptr, *recoveryRow = nullptr;
    QComboBox *backup = nullptr;
    QLabel *review = nullptr, *status = nullptr;
    QProgressBar *progress = nullptr;
    QTextEdit *details = nullptr;
    QLineEdit *confirmation = nullptr;
    QProcess process;
    QByteArray pending;
    bool running = false, started = false;
};

#include "main.moc"

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("Aether Installer"));
    const QStringList arguments = app.arguments();
    const int flag = arguments.indexOf(QStringLiteral("--screenshot"));
    if (flag > 0 && flag + 2 < arguments.size()) {
        Installer window;
        window.setStartPage(arguments.at(flag + 1));
        window.show();
        app.processEvents();
        window.grab().save(arguments.at(flag + 2));
        return 0;
    }
    if (arguments.contains(QStringLiteral("--welcome"))) {
        QDialog chooser;
        chooser.setWindowTitle(QStringLiteral("Aether Linux 0.3"));
        chooser.setModal(true);
        chooser.setFixedWidth(430);
        chooser.setStyleSheet(QStringLiteral(R"(
            QDialog { background: #f5f7fc; }
            QLabel { color: #1a2133; font-size: 13px; }
            QPushButton { background: #edf0f8; border: 1px solid #d8ddec; border-radius: 9px;
                          padding: 9px 20px; color: #232b3f; font-weight: 500; }
            QPushButton:hover { background: #e3e8f5; }
            QPushButton#install { background: #5b6cf9; border-color: #5b6cf9; color: #ffffff; }
            QPushButton#install:hover { background: #4c5de8; }
        )"));
        auto *chooserLayout = new QVBoxLayout(&chooser);
        chooserLayout->setContentsMargins(30, 28, 30, 24);
        chooserLayout->setSpacing(10);
        auto *logo = new QLabel;
        logo->setPixmap(renderLogo(76));
        logo->setAlignment(Qt::AlignCenter);
        chooserLayout->addWidget(logo, 0, Qt::AlignHCenter);
        auto *title = new QLabel(QStringLiteral(
            "<span style=\"font-size:22px;font-weight:600;color:#151b2c\">Aether Linux 0.3</span>"));
        title->setAlignment(Qt::AlignCenter);
        chooserLayout->addWidget(title);
        auto *body = new QLabel(QStringLiteral("Try Aether without changing this computer, or install it now."));
        body->setWordWrap(true);
        body->setAlignment(Qt::AlignCenter);
        body->setStyleSheet(QStringLiteral("color:#5b6478;font-size:13px;"));
        chooserLayout->addWidget(body);
        chooserLayout->addSpacing(6);
        auto *buttons = new QHBoxLayout;
        buttons->setSpacing(10);
        auto *tryButton = new QPushButton(QStringLiteral("Try Aether"));
        auto *installButton = new QPushButton(QStringLiteral("Install Aether"));
        installButton->setObjectName(QStringLiteral("install"));
        installButton->setDefault(true);
        buttons->addWidget(tryButton);
        buttons->addWidget(installButton);
        chooserLayout->addLayout(buttons);
        bool install = false;
        QObject::connect(tryButton, &QPushButton::clicked, &chooser, &QDialog::reject);
        QObject::connect(installButton, &QPushButton::clicked, &chooser, [&chooser, &install] {
            install = true;
            chooser.accept();
        });
        chooser.exec();
        if (!install) return 0;
        Installer window;
        window.setStartPage(QStringLiteral("region"));
        window.show();
        return app.exec();
    }
    Installer window;
    window.show();
    return app.exec();
}
