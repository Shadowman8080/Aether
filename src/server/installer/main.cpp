// SPDX-License-Identifier: GPL-2.0-or-later
//
// Aether Server graphical installer.
//
// A Qt 6 wizard over the same privileged backend as the desktop installer
// (/usr/libexec/aether-server-install-backend). The installer is deliberately
// data-driven: the server roles are read at runtime from the role catalog
// (/usr/share/aether/server/roles.json), so a new role is a catalog entry plus
// its configuration templates rather than a change to this program.

#include <QApplication>
#include <QButtonGroup>
#include <QCheckBox>
#include <QCloseEvent>
#include <QComboBox>
#include <QColor>
#include <QFile>
#include <QFileInfo>
#include <QFormLayout>
#include <QHash>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QPixmap>
#include <QProcess>
#include <QProgressBar>
#include <QPushButton>
#include <QRadioButton>
#include <QRegularExpression>
#include <QSvgRenderer>
#include <QTextBrowser>
#include <QTextEdit>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QVBoxLayout>
#include <QWizard>

#include <initializer_list>

namespace {

constexpr auto kCatalogPath = "/usr/share/aether/server/roles.json";
constexpr auto kBackend = "/usr/libexec/aether-server-install-backend";

QJsonObject loadCatalog() {
    const QByteArray override = qgetenv("AETHER_SERVER_CATALOG");
    const QString path = override.isEmpty() ? QString::fromLatin1(kCatalogPath)
                                            : QString::fromUtf8(override);
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return {};
    return QJsonDocument::fromJson(file.readAll()).object();
}

}  // namespace

class ServerInstaller final : public QWizard {
    // Region
    QComboBox *keyboard = nullptr, *timezone = nullptr;
    // Network
    QLineEdit *hostname = nullptr, *address = nullptr, *gateway = nullptr, *dns = nullptr, *netInterface = nullptr;
    QRadioButton *dhcp = nullptr, *staticAddress = nullptr;
    // Storage
    QComboBox *disks = nullptr;
    QLineEdit *storage = nullptr, *recovery = nullptr, *repeatStorage = nullptr, *repeatRecovery = nullptr;
    QCheckBox *encrypt = nullptr, *savedRecovery = nullptr;
    // Roles
    QTreeWidget *roleTree = nullptr;
    QTextBrowser *roleDetails = nullptr;
    QLabel *roleCount = nullptr;
    QHash<QString, QJsonObject> roleById;
    // Directory
    QCheckBox *joinAd = nullptr;
    QLineEdit *adDomain = nullptr, *adUser = nullptr, *adPassword = nullptr, *adComputer = nullptr;
    // Account
    QLineEdit *username = nullptr, *password = nullptr, *repeatPassword = nullptr;
    // Review / install
    QLabel *review = nullptr, *status = nullptr;
    QLineEdit *confirmation = nullptr;
    QProgressBar *progress = nullptr;
    QTextEdit *details = nullptr;
    QProcess process;
    QByteArray pending;
    bool running = false, started = false;

    QWizardPage *page(const QString &title, const QString &subtitle) {
        auto *p = new QWizardPage;
        p->setTitle(title);
        p->setSubTitle(subtitle);
        addPage(p);
        return p;
    }

    QLineEdit *secret(QFormLayout *form, const QString &label) {
        auto *field = new QLineEdit;
        field->setEchoMode(QLineEdit::Password);
        field->setMaxLength(1024);
        field->setAccessibleName(label);
        field->setInputMethodHints(Qt::ImhSensitiveData | Qt::ImhNoPredictiveText);
        form->addRow(label, field);
        return field;
    }

    static bool mounted(const QJsonObject &node) {
        for (const auto &point : node["mountpoints"].toArray())
            if (!point.isNull() && !point.toString().isEmpty()) return true;
        for (const auto &child : node["children"].toArray())
            if (mounted(child.toObject())) return true;
        return false;
    }

    void refreshDisks() {
        disks->clear();
        QProcess list;
        list.start("/usr/bin/lsblk", {"-J", "-b", "-o", "PATH,SIZE,MODEL,TYPE,RO,MOUNTPOINTS"});
        if (!list.waitForFinished(5000) || list.exitCode() != 0) return;
        for (const auto &entry : QJsonDocument::fromJson(list.readAllStandardOutput()).object()["blockdevices"].toArray()) {
            const auto disk = entry.toObject();
            const double size = disk["size"].toVariant().toDouble();
            if (disk["type"].toString() != "disk" || disk["ro"].toVariant().toBool() || mounted(disk) ||
                size < 16.0 * 1024 * 1024 * 1024) continue;
            const QString path = disk["path"].toString();
            disks->addItem(QString("%1  ·  %2 GiB  ·  %3")
                               .arg(path)
                               .arg(size / (1024 * 1024 * 1024), 0, 'f', 1)
                               .arg(disk["model"].toString().trimmed()),
                           path);
        }
        if (!disks->count())
            disks->addItem(tr("No eligible disk. Attach an empty disk of at least 16 GiB."), QString());
    }

    QString problem() const {
        if (currentId() == 2) {
            if (hostname->text().trimmed().isEmpty()) return tr("Enter a hostname for this server.");
            if (!QRegularExpression("^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$").match(hostname->text().trimmed()).hasMatch())
                return tr("The hostname may contain only letters, digits and hyphens.");
            if (staticAddress->isChecked() && address->text().trimmed().isEmpty())
                return tr("Enter a static IPv4 address in CIDR form, such as 10.0.0.10/24.");
        }
        if (currentId() == 3 && disks->currentData().toString().isEmpty())
            return tr("Select an unmounted, writable disk of at least 16 GiB.");
        if (currentId() == 3 && encrypt->isChecked() &&
            (storage->text().size() < 12 || recovery->text().size() < 12 ||
             storage->text() == recovery->text() || storage->text() != repeatStorage->text() ||
             recovery->text() != repeatRecovery->text() || !savedRecovery->isChecked()))
            return tr("Use different storage and recovery passphrases of at least twelve characters, and confirm you saved the recovery passphrase.");
        if (currentId() == 5 && joinAd->isChecked()) {
            if (adDomain->text().trimmed().isEmpty()) return tr("Enter the Active Directory domain to join.");
            if (adUser->text().trimmed().isEmpty()) return tr("Enter a domain account allowed to join the domain.");
        }
        if (currentId() == 6) {
            if (!QRegularExpression("^[a-z][a-z0-9_-]{0,30}$").match(username->text()).hasMatch())
                return tr("Use a lowercase administrator name, starting with a letter.");
            if (password->text().size() < 12 || password->text() != repeatPassword->text())
                return tr("Enter matching administrator passwords with at least twelve characters.");
        }
        if (currentId() == 7 && confirmation->text() != "ERASE " + disks->currentData().toString())
            return tr("Type the exact confirmation shown above to erase the selected disk.");
        return {};
    }

    QStringList selectedRoles() const {
        QStringList roles;
        for (int i = 0; i < roleTree->topLevelItemCount(); ++i) {
            QTreeWidgetItem *category = roleTree->topLevelItem(i);
            for (int j = 0; j < category->childCount(); ++j) {
                QTreeWidgetItem *item = category->child(j);
                if (item->checkState(0) == Qt::Checked)
                    roles << item->data(0, Qt::UserRole).toString();
            }
        }
        return roles;
    }

    void showRoleDetails(QTreeWidgetItem *item) {
        if (!item || !roleById.contains(item->data(0, Qt::UserRole).toString())) {
            roleDetails->clear();
            return;
        }
        const QJsonObject role = roleById.value(item->data(0, Qt::UserRole).toString());
        QStringList packages, services, firewall;
        for (const auto &p : role["packages"].toArray()) packages << p.toString();
        for (const auto &s : role["services"].toArray()) services << s.toString();
        for (const auto &f : role["firewall"].toArray()) firewall << f.toString();
        QString html = QString("<h3>%1</h3>").arg(role["name"].toString().toHtmlEscaped());
        html += QString("<p>%1</p>").arg(role["summary"].toString().toHtmlEscaped());
        if (!packages.isEmpty()) html += QString("<p><b>Software:</b> %1</p>").arg(packages.join(", ").toHtmlEscaped());
        if (!services.isEmpty()) html += QString("<p><b>Services:</b> %1</p>").arg(services.join(", ").toHtmlEscaped());
        if (!firewall.isEmpty()) html += QString("<p><b>Opens:</b> %1</p>").arg(firewall.join(", ").toHtmlEscaped());
        const QString notes = role["notes"].toString();
        if (!notes.isEmpty()) html += QString("<p><b>Note:</b> %1</p>").arg(notes.toHtmlEscaped());
        roleDetails->setHtml(html);
    }

    void updateRoleCount() {
        roleCount->setText(tr("%n server role(s) selected", "", selectedRoles().size()));
    }

    void buildRolePage(QWizardPage *rolePage) {
        const QJsonObject catalog = loadCatalog();
        auto *layout = new QVBoxLayout(rolePage);
        auto *intro = new QLabel(tr("Choose what this server will do. Roles are configured during installation; "
                                    "a role whose software is not present in this image is reported rather than failed."));
        intro->setWordWrap(true);
        layout->addWidget(intro);

        auto *controls = new QHBoxLayout;
        auto *recommended = new QPushButton(tr("Select recommended"));
        auto *everything = new QPushButton(tr("Select all"));
        auto *clear = new QPushButton(tr("Clear all"));
        controls->addWidget(recommended);
        controls->addWidget(everything);
        controls->addWidget(clear);
        controls->addStretch();
        layout->addLayout(controls);

        auto *split = new QHBoxLayout;
        roleTree = new QTreeWidget;
        roleTree->setHeaderHidden(true);
        roleTree->setColumnCount(1);
        roleDetails = new QTextBrowser;
        roleDetails->setOpenExternalLinks(false);
        split->addWidget(roleTree, 3);
        split->addWidget(roleDetails, 2);
        layout->addLayout(split, 1);
        roleCount = new QLabel;
        layout->addWidget(roleCount);

        for (const auto &categoryValue : catalog["categories"].toArray()) {
            const QJsonObject category = categoryValue.toObject();
            auto *node = new QTreeWidgetItem(roleTree);
            node->setText(0, category["name"].toString());
            node->setFlags(node->flags() & ~Qt::ItemIsSelectable);
            node->setExpanded(true);
            for (const auto &roleValue : catalog["roles"].toArray()) {
                const QJsonObject role = roleValue.toObject();
                if (role["category"].toString() != category["id"].toString()) continue;
                auto *item = new QTreeWidgetItem(node);
                item->setText(0, role["name"].toString());
                item->setData(0, Qt::UserRole, role["id"].toString());
                item->setFlags(item->flags() | Qt::ItemIsUserCheckable);
                item->setCheckState(0, role["default"].toBool() ? Qt::Checked : Qt::Unchecked);
                roleById.insert(role["id"].toString(), role);
            }
        }
        if (roleById.isEmpty()) {
            auto *warning = new QLabel(tr("The server role catalog could not be read. "
                                          "Only the base system will be installed."));
            warning->setWordWrap(true);
            layout->insertWidget(0, warning);
        }

        connect(roleTree, &QTreeWidget::currentItemChanged, this,
                [this](QTreeWidgetItem *current, QTreeWidgetItem *) { showRoleDetails(current); });
        connect(roleTree, &QTreeWidget::itemChanged, this,
                [this](QTreeWidgetItem *, int) { updateRoleCount(); });
        connect(recommended, &QPushButton::clicked, this, [this] {
            for (int i = 0; i < roleTree->topLevelItemCount(); ++i)
                for (int j = 0; j < roleTree->topLevelItem(i)->childCount(); ++j) {
                    auto *item = roleTree->topLevelItem(i)->child(j);
                    const auto role = roleById.value(item->data(0, Qt::UserRole).toString());
                    item->setCheckState(0, role["recommended"].toBool() ? Qt::Checked : Qt::Unchecked);
                }
        });
        connect(everything, &QPushButton::clicked, this, [this](bool) {
            for (int i = 0; i < roleTree->topLevelItemCount(); ++i)
                for (int j = 0; j < roleTree->topLevelItem(i)->childCount(); ++j)
                    roleTree->topLevelItem(i)->child(j)->setCheckState(0, Qt::Checked);
        });
        connect(clear, &QPushButton::clicked, this, [this] {
            for (int i = 0; i < roleTree->topLevelItemCount(); ++i)
                for (int j = 0; j < roleTree->topLevelItem(i)->childCount(); ++j)
                    roleTree->topLevelItem(i)->child(j)->setCheckState(0, Qt::Unchecked);
        });
        updateRoleCount();
    }

    void install() {
        if (started) return;
        started = true;
        if (!QFileInfo::exists("/run/initramfs/live/lower/etc/os-release")) {
            status->setText(tr("Boot the Aether Server live ISO to install. No disk was changed."));
            button(FinishButton)->setEnabled(true);
            return;
        }
        QJsonObject network{{"mode", dhcp->isChecked() ? "dhcp" : "static"},
                            {"address", address->text().trimmed()},
                            {"gateway", gateway->text().trimmed()},
                            {"dns", dns->text().trimmed()},
                            {"interface", netInterface->text().trimmed()}};
        QJsonArray roles;
        for (const QString &role : selectedRoles()) roles.append(role);
        QJsonObject directory{{"join", joinAd->isChecked()},
                              {"domain", adDomain->text().trimmed()},
                              {"join_user", adUser->text().trimmed()},
                              {"join_password", adPassword->text()},
                              {"computer_name", adComputer->text().trimmed()}};
        QJsonObject config{{"disk", disks->currentData().toString()},
                           {"hostname", hostname->text().trimmed()},
                           {"username", username->text()},
                           {"password", password->text()},
                           {"encrypt", encrypt->isChecked()},
                           {"storage_password", storage->text()},
                           {"recovery_password", recovery->text()},
                           {"timezone", timezone->currentText()},
                           {"keyboard", keyboard->currentData().toString()},
                           {"language", "en_US.UTF-8"},
                           {"network", network},
                           {"roles", roles},
                           {"directory", directory},
                           {"confirmation", confirmation->text()}};

        running = true;
        button(BackButton)->setEnabled(false);
        button(CancelButton)->setEnabled(false);
        button(FinishButton)->setEnabled(false);
        progress->setRange(0, 9);
        progress->setValue(0);
        status->setText(tr("Authorize installation to begin…"));
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start("/usr/bin/pkexec", {QString::fromLatin1(kBackend), "--graphical"});
        if (!process.waitForStarted(5000)) {
            running = false;
            status->setText(tr("The installation service could not start. No disk was changed."));
            button(FinishButton)->setEnabled(true);
            return;
        }
        process.write(QJsonDocument(config).toJson(QJsonDocument::Compact));
        process.closeWriteChannel();
        password->clear();
        repeatPassword->clear();
        storage->clear();
        recovery->clear();
        repeatStorage->clear();
        repeatRecovery->clear();
        adPassword->clear();
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
        if (id == 3) refreshDisks();
        if (id == 7) {
            review->setText(tr(
                "Hostname: %1\nNetwork: %2\nAdministrator: %3\nTime zone: %4\nKeyboard: %5\n"
                "System encryption: %6\nServer roles: %7\nDirectory join: %8\n\n"
                "Disk: %9\nAll partitions and files on this disk will be erased.\n\n"
                "Type ERASE %9 below to confirm. /boot remains unencrypted and Secure Boot is not yet supported.")
                .arg(hostname->text().trimmed(),
                     dhcp->isChecked() ? tr("DHCP") : tr("Static %1").arg(address->text().trimmed()),
                     username->text(),
                     timezone->currentText(),
                     keyboard->currentText(),
                     encrypt->isChecked() ? tr("LUKS2") : tr("Off"),
                     selectedRoles().isEmpty() ? tr("None selected") : selectedRoles().join(", "),
                     joinAd->isChecked() ? adDomain->text().trimmed() : tr("No"),
                     disks->currentData().toString()));
            confirmation->clear();
            setButtonText(NextButton, tr("Erase disk and install Aether Server"));
        } else {
            setButtonText(NextButton, tr("Continue"));
        }
        if (id == 8) install();
    }

    void closeEvent(QCloseEvent *event) override {
        if (running) event->ignore();
        else QWizard::closeEvent(event);
    }

    void reject() override {
        if (!running) QWizard::reject();
    }

public:
    ServerInstaller() {
        setWindowTitle(tr("Install Aether Server"));
        resize(1000, 720);
        setWizardStyle(QWizard::ModernStyle);
        setOption(QWizard::NoBackButtonOnStartPage);
        setOption(QWizard::NoBackButtonOnLastPage);
        setButtonText(FinishButton, tr("Close"));
        setStyleSheet(
            "QWizard {background:#f4f5fb;color:#22263b;} QWizardPage {background:transparent;}"
            "QLabel {color:#22263b;} QLineEdit,QComboBox,QTextEdit,QTextBrowser {background:white;"
            "color:#22263b;padding:6px;border:1px solid #bdc2d8;border-radius:7px;}"
            "QTreeWidget {background:white;border:1px solid #bdc2d8;border-radius:7px;}"
            "QPushButton {padding:8px 16px;background:#d9dbff;border:1px solid #adb2d7;border-radius:8px;"
            "color:#22263b;} QPushButton:disabled {color:#8e94a8;}"
            "QProgressBar {border:1px solid #bdc2d8;border-radius:6px;text-align:center;}"
            "QProgressBar::chunk {background:#798bea;}");

        QPixmap banner(190, 620);
        banner.fill(QColor("#17213d"));
        {
            QPainter painter(&banner);
            QSvgRenderer logo(QStringLiteral("/usr/share/icons/hicolor/scalable/apps/aether-logo.svg"));
            logo.render(&painter, QRectF(46, 42, 96, 96));
            painter.setPen(Qt::white);
            painter.drawText(QRect(15, 170, 160, 430), Qt::AlignTop | Qt::AlignHCenter,
                             tr("AETHER\nSERVER\n\nWelcome\n\nYour region\n\nNetwork\n\nStorage\n\n"
                                "Server roles\n\nDirectory\n\nAdministrator\n\nReview\n\nInstall"));
        }
        setPixmap(QWizard::WatermarkPixmap, banner);

        auto *welcome = page(tr("Build your server"), tr("Aether Server installs a base system, then configures the roles you choose."));
        auto *welcomeLayout = new QVBoxLayout(welcome);
        auto *intro = new QLabel(tr(
            "This installer will set up the network, choose a disk, install the base system, and configure the "
            "server roles you select — DHCP, DNS, web, database, mail, directory services and more — plus an "
            "optional Active Directory join.\n\n"
            "You can try the live system before installing. No disk changes happen until you review your choices "
            "and confirm installation.\n\n"
            "This preview installs to an entire disk. Manual partitioning and alongside-another-OS installation "
            "are not available yet.\n\nInstaller language: English"));
        intro->setWordWrap(true);
        welcomeLayout->addWidget(intro);
        welcomeLayout->addStretch();

        auto *region = page(tr("Your region"), tr("These settings will apply to the installed server."));
        auto *regionForm = new QFormLayout(region);
        keyboard = new QComboBox;
        for (const auto &pair : QList<QPair<QString, QString>>{{"English (US)", "us"}, {"English (UK)", "gb"},
                                                               {"German", "de"}, {"French", "fr"}, {"Spanish", "es"},
                                                               {"Italian", "it"}, {"Portuguese", "pt"}, {"Portuguese (Brazil)", "br"}})
            keyboard->addItem(pair.first, pair.second);
        timezone = new QComboBox;
        timezone->addItem("UTC");
        QFile zones("/usr/share/zoneinfo/zone.tab");
        QStringList names;
        if (zones.open(QIODevice::ReadOnly))
            for (const auto &line : zones.readAll().split('\n')) {
                if (line.startsWith('#')) continue;
                const auto fields = line.split('\t');
                if (fields.size() > 2) names.append(QString::fromUtf8(fields[2]));
            }
        names.sort();
        timezone->addItems(names);
        regionForm->addRow(tr("Keyboard layout"), keyboard);
        regionForm->addRow(tr("Time zone"), timezone);

        auto *networkPage = page(tr("Network"), tr("A server should have a predictable address and name."));
        auto *networkForm = new QFormLayout(networkPage);
        hostname = new QLineEdit("aether-server");
        hostname->setMaxLength(63);
        networkForm->addRow(tr("Hostname"), hostname);
        dhcp = new QRadioButton(tr("Automatic (DHCP)"));
        staticAddress = new QRadioButton(tr("Static IPv4 address"));
        dhcp->setChecked(true);
        auto *mode = new QButtonGroup(this);
        mode->addButton(dhcp);
        mode->addButton(staticAddress);
        networkForm->addRow(tr("Addressing"), dhcp);
        networkForm->addRow("", staticAddress);
        address = new QLineEdit;
        address->setPlaceholderText(tr("10.0.0.10/24"));
        gateway = new QLineEdit;
        gateway->setPlaceholderText(tr("10.0.0.1 (optional)"));
        dns = new QLineEdit;
        dns->setPlaceholderText(tr("1.1.1.1, 9.9.9.9 (optional)"));
        netInterface = new QLineEdit;
        netInterface->setPlaceholderText(tr("eth0 (optional; any interface if empty)"));
        networkForm->addRow(tr("IPv4 address"), address);
        networkForm->addRow(tr("Gateway"), gateway);
        networkForm->addRow(tr("DNS servers"), dns);
        networkForm->addRow(tr("Interface"), netInterface);
        auto enableStatic = [this](bool on) {
            address->setEnabled(on);
            gateway->setEnabled(on);
            dns->setEnabled(on);
            netInterface->setEnabled(on);
        };
        connect(staticAddress, &QRadioButton::toggled, this, enableStatic);
        enableStatic(false);

        auto *storagePage = page(tr("Choose storage"), tr("Only unmounted, writable whole disks of at least 16 GiB are listed."));
        auto *storageLayout = new QVBoxLayout(storagePage);
        disks = new QComboBox;
        disks->setAccessibleName(tr("Installation disk"));
        storageLayout->addWidget(disks);
        auto *refresh = new QPushButton(tr("Refresh disks"));
        storageLayout->addWidget(refresh);
        connect(refresh, &QPushButton::clicked, this, [this] { refreshDisks(); });
        auto *erase = new QLabel(tr("Erase the disk and install Aether Server\n\nEvery partition and file on the selected disk will be removed. "
                                    "Other disks are left unchanged. Review the device name and size carefully."));
        erase->setWordWrap(true);
        storageLayout->addWidget(erase);
        encrypt = new QCheckBox(tr("Encrypt system storage (LUKS2)"));
        storageLayout->addWidget(encrypt);
        auto *passwords = new QFormLayout;
        auto secretPair = [&passwords](const QString &label, QLineEdit *&first, QLineEdit *&second) {
            auto *row = new QWidget;
            auto *layout = new QHBoxLayout(row);
            layout->setContentsMargins(0, 0, 0, 0);
            first = new QLineEdit;
            second = new QLineEdit;
            for (auto *entry : {first, second}) {
                entry->setEchoMode(QLineEdit::Password);
                entry->setMaxLength(1024);
                entry->setInputMethodHints(Qt::ImhSensitiveData | Qt::ImhNoPredictiveText);
                layout->addWidget(entry);
            }
            first->setAccessibleName(label);
            second->setAccessibleName(label + QStringLiteral(" confirmation"));
            second->setPlaceholderText(tr("Confirm"));
            passwords->addRow(label, row);
        };
        secretPair(tr("Storage passphrase"), storage, repeatStorage);
        secretPair(tr("Recovery passphrase"), recovery, repeatRecovery);
        savedRecovery = new QCheckBox(tr("I saved the different recovery passphrase in a safe place"));
        passwords->addRow(savedRecovery);
        storageLayout->addLayout(passwords);
        storageLayout->addStretch();
        auto enableEncryption = [this](bool on) {
            for (auto *widget : std::initializer_list<QWidget *>{storage, recovery, repeatStorage, repeatRecovery,
                                                                savedRecovery})
                widget->setEnabled(on);
        };
        connect(encrypt, &QCheckBox::toggled, this, enableEncryption);
        enableEncryption(false);

        auto *rolePage = page(tr("Server roles"), tr("Select the services this machine should run."));
        buildRolePage(rolePage);

        auto *directoryPage = page(tr("Directory and identity"), tr("Optionally join an existing Active Directory domain."));
        auto *directoryLayout = new QVBoxLayout(directoryPage);
        joinAd = new QCheckBox(tr("Join this server to an Active Directory domain"));
        directoryLayout->addWidget(joinAd);
        auto *directoryForm = new QFormLayout;
        adDomain = new QLineEdit;
        adDomain->setPlaceholderText(tr("example.lan"));
        adUser = new QLineEdit;
        adUser->setPlaceholderText(tr("administrator or a delegated join account"));
        adPassword = secret(directoryForm, tr("Domain account password"));
        adComputer = new QLineEdit;
        adComputer->setPlaceholderText(tr("Optional; defaults to the hostname"));
        directoryForm->addRow(tr("Domain"), adDomain);
        directoryForm->addRow(tr("Join account"), adUser);
        directoryForm->addRow(tr("Computer name"), adComputer);
        directoryLayout->addLayout(directoryForm);
        auto *directoryNote = new QLabel(tr(
            "The installer writes Kerberos, sssd and PAM configuration and enables sssd. If the adcli join tool "
            "is present it performs the machine-account join now; otherwise the configuration is written and you "
            "finish the join after boot with: sudo aether-directory join DOMAIN --user ACCOUNT. Local accounts "
            "keep working either way."));
        directoryNote->setWordWrap(true);
        directoryLayout->addWidget(directoryNote);
        directoryLayout->addStretch();
        auto enableDirectory = [this](bool on) {
            for (auto *widget : std::initializer_list<QWidget *>{adDomain, adUser, adPassword, adComputer})
                widget->setEnabled(on);
        };
        connect(joinAd, &QCheckBox::toggled, this, enableDirectory);
        enableDirectory(false);

        auto *accountPage = page(tr("Administrator"), tr("This account administers the server through sudo and over SSH."));
        auto *accountForm = new QFormLayout(accountPage);
        username = new QLineEdit("aether");
        username->setMaxLength(31);
        accountForm->addRow(tr("Administrator name"), username);
        password = secret(accountForm, tr("Administrator password"));
        repeatPassword = secret(accountForm, tr("Confirm password"));
        auto *accountNote = new QLabel(tr("The account is added to the wheel group and may run commands as root with sudo. "
                                          "The root account is locked; sign in as the administrator."));
        accountNote->setWordWrap(true);
        accountForm->addRow(accountNote);

        auto *reviewPage = page(tr("Ready to install?"), tr("Review these choices before making any disk changes."));
        auto *reviewLayout = new QVBoxLayout(reviewPage);
        review = new QLabel;
        review->setWordWrap(true);
        review->setTextFormat(Qt::PlainText);
        reviewLayout->addWidget(review);
        confirmation = new QLineEdit;
        confirmation->setAccessibleName(tr("Disk erase confirmation"));
        reviewLayout->addWidget(confirmation);
        reviewLayout->addStretch();

        auto *installPage = page(tr("Installing Aether Server"), tr("Keep this window open and the computer powered on."));
        auto *installLayout = new QVBoxLayout(installPage);
        status = new QLabel;
        status->setWordWrap(true);
        installLayout->addWidget(status);
        progress = new QProgressBar;
        installLayout->addWidget(progress);
        details = new QTextEdit;
        details->setReadOnly(true);
        installLayout->addWidget(details);

        connect(&process, &QProcess::readyReadStandardOutput, this, [this] {
            pending += process.readAllStandardOutput();
            int end;
            while ((end = pending.indexOf('\n')) >= 0) {
                const QByteArray line = pending.left(end);
                pending.remove(0, end + 1);
                if (line.startsWith("AETHER_PROGRESS ")) {
                    const auto entry = QJsonDocument::fromJson(line.mid(16)).object();
                    progress->setValue(entry["step"].toInt());
                    status->setText(entry["message"].toString());
                } else {
                    details->append(QString::fromUtf8(line).toHtmlEscaped());
                }
            }
        });
        connect(&process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this,
                [this](int code, QProcess::ExitStatus state) {
                    running = false;
                    button(FinishButton)->setEnabled(true);
                    button(CancelButton)->setEnabled(false);
                    status->setText(code == 0 && state == QProcess::NormalExit
                                        ? tr("Aether Server is installed. Shut down, remove the ISO, then start your new system.")
                                        : tr("Installation did not complete. Review the details below. Do not assume the disk is unchanged if installation had started."));
                });
    }
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.setApplicationName("Aether Server Installer");
    ServerInstaller window;
    window.show();
    return app.exec();
}
