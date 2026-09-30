// SPDX-License-Identifier: GPL-2.0-or-later
#include <QApplication>
#include <QCheckBox>
#include <QCloseEvent>
#include <QComboBox>
#include <QFile>
#include <QFileInfo>
#include <QFormLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QProcess>
#include <QProgressBar>
#include <QPushButton>
#include <QRegularExpression>
#include <QSvgRenderer>
#include <QTextEdit>
#include <QVBoxLayout>
#include <QWizard>

class Installer final : public QWizard {
    QComboBox *disks, *keyboard, *timezone;
    QLineEdit *username, *password, *repeatPassword, *storage, *recovery, *backup, *confirmation, *repeatStorage, *repeatRecovery;
    QCheckBox *encrypt, *savedRecovery;
    QLabel *review, *status;
    QProgressBar *progress;
    QTextEdit *details;
    QProcess process;
    QByteArray pending;
    bool running = false, started = false;
    QWizardPage *page(const QString &title, const QString &subtitle) {
        auto p = new QWizardPage; p->setTitle(title); p->setSubTitle(subtitle);
        addPage(p); return p;
    }
    QLineEdit *secret(QFormLayout *form, const QString &label) {
        auto field = new QLineEdit; field->setEchoMode(QLineEdit::Password);
        field->setMaxLength(1024); field->setAccessibleName(label);
        field->setInputMethodHints(Qt::ImhSensitiveData | Qt::ImhNoPredictiveText);
        form->addRow(label, field); return field;
    }
    static bool mounted(const QJsonObject &node) {
        for (const auto &point : node["mountpoints"].toArray()) if (!point.isNull() && !point.toString().isEmpty()) return true;
        for (const auto &child : node["children"].toArray()) if (mounted(child.toObject())) return true;
        return false;
    }
    void refreshDisks() {
        disks->clear(); QProcess list;
        list.start("/usr/bin/lsblk", {"-J", "-b", "-o", "PATH,SIZE,MODEL,TYPE,RO,MOUNTPOINTS"});
        if (!list.waitForFinished(5000) || list.exitCode() != 0) return;
        for (const auto &entry : QJsonDocument::fromJson(list.readAllStandardOutput()).object()["blockdevices"].toArray()) {
            const auto disk = entry.toObject(); const double size = disk["size"].toVariant().toDouble();
            if (disk["type"].toString() != "disk" || disk["ro"].toVariant().toBool() || mounted(disk) || size < 16.0*1024*1024*1024) continue;
            const QString path = disk["path"].toString();
            disks->addItem(QString("%1  ·  %2 GiB  ·  %3").arg(path).arg(size/(1024*1024*1024),0,'f',1).arg(disk["model"].toString().trimmed()), path);
        }
        if (!disks->count()) disks->addItem(tr("No eligible disk. Attach an empty disk of at least 16 GiB."), QString());
    }
    QString problem() const {
        if (currentId() == 2 && disks->currentData().toString().isEmpty()) return tr("Select an unmounted, writable disk of at least 16 GiB.");
        if (currentId() == 3) {
            if (!QRegularExpression("^[a-z][a-z0-9_-]{0,30}$").match(username->text()).hasMatch()) return tr("Use a lowercase account name, starting with a letter.");
            if (password->text().size() < 12 || password->text() != repeatPassword->text()) return tr("Enter matching account passwords with at least twelve characters.");
            if (encrypt->isChecked() && (storage->text().size()<12 || recovery->text().size()<12 || storage->text()==recovery->text() || storage->text()!=repeatStorage->text() || recovery->text()!=repeatRecovery->text() || !savedRecovery->isChecked()))
                return tr("Use different storage and recovery passphrases of at least twelve characters, and confirm you saved the recovery passphrase.");
            if (!backup->text().isEmpty() && !backup->text().startsWith('/')) return tr("Enter an absolute Linux path for backups, or leave it empty to set up later.");
        }
        if (currentId() == 4 && confirmation->text() != "ERASE " + disks->currentData().toString()) return tr("Type the exact confirmation shown above to erase the selected disk.");
        return {};
    }
    void install() {
        if (started) return;
        started = true;
        if (!QFileInfo::exists("/run/initramfs/live/lower/etc/os-release")) {
            status->setText(tr("Boot the Aether live ISO to install. No disk was changed."));
            button(FinishButton)->setEnabled(true); return;
        }
        QJsonObject config{{"disk", disks->currentData().toString()}, {"username",username->text()},
            {"password",password->text()}, {"encrypt",encrypt->isChecked()}, {"storage_password",storage->text()},
            {"recovery_password",recovery->text()}, {"backup",backup->text()}, {"confirmation",confirmation->text()},
            {"timezone",timezone->currentText()}, {"keyboard",keyboard->currentData().toString()}, {"language","en_US.UTF-8"}};
        running = true; button(BackButton)->setEnabled(false); button(CancelButton)->setEnabled(false); button(FinishButton)->setEnabled(false);
        progress->setRange(0,0); status->setText(tr("Authorize installation to begin…"));
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start("/usr/bin/pkexec", {"/usr/libexec/aether-installer-backend", "--graphical"});
        if (!process.waitForStarted(5000)) { running=false; status->setText(tr("The installation service could not start. No disk was changed.")); button(FinishButton)->setEnabled(true); return; }
        process.write(QJsonDocument(config).toJson(QJsonDocument::Compact)); process.closeWriteChannel();
        password->clear(); repeatPassword->clear(); storage->clear(); recovery->clear(); repeatStorage->clear(); repeatRecovery->clear();
    }
protected:
    bool validateCurrentPage() override {
        const QString error=problem();
        if (!error.isEmpty()) { QMessageBox::warning(this,tr("Check your choices"),error); return false; }
        return !running;
    }
    void initializePage(int id) override {
        QWizard::initializePage(id);
        if (id==2) refreshDisks();
        if (id==4) {
            const QString disk=disks->currentData().toString();
            review->setText(tr("Disk: %1\nAll partitions and files on this disk will be erased.\n\nAccount: %2\nTime zone: %3\nKeyboard: %4\nStorage encryption: %5\nBackups: %6\n\nType ERASE %1 below to confirm.\nBoot files remain unencrypted. Secure Boot is not yet supported.")
                .arg(disk,username->text(),timezone->currentText(),keyboard->currentText(),encrypt->isChecked()?tr("LUKS2"):tr("Off"),backup->text().isEmpty()?tr("Set up after installation"):backup->text()));
            confirmation->clear(); setButtonText(NextButton,tr("Erase disk and install"));
        } else setButtonText(NextButton,tr("Continue"));
        if (id==5) install();
    }
    void closeEvent(QCloseEvent *event) override { if (running) event->ignore(); else QWizard::closeEvent(event); }
    void reject() override { if (!running) QWizard::reject(); }
public:
    Installer() {
        setWindowTitle(tr("Install Aether Linux")); resize(940,680); setWizardStyle(QWizard::ModernStyle);
        setOption(QWizard::NoBackButtonOnStartPage); setOption(QWizard::NoBackButtonOnLastPage);
        setButtonText(FinishButton,tr("Close"));
        setStyleSheet("QWizard {background:#f4f5fb;color:#22263b;} QWizardPage {background:transparent;} QLabel {color:#22263b;} QLineEdit,QComboBox,QTextEdit {background:white;color:#22263b;padding:8px;border:1px solid #bdc2d8;border-radius:7px;} QPushButton {padding:9px 20px;background:#d9dbff;border:1px solid #adb2d7;border-radius:8px;color:#22263b;} QPushButton:disabled {color:#8e94a8;} QProgressBar {border:1px solid #bdc2d8;border-radius:6px;text-align:center;} QProgressBar::chunk {background:#798bea;} ");
        QPixmap banner(180,500); banner.fill(QColor("#17213d")); { QPainter painter(&banner); QSvgRenderer logo(QStringLiteral("/usr/share/icons/hicolor/scalable/apps/aether-logo.svg")); logo.render(&painter,QRectF(42,42,96,96)); painter.setPen(Qt::white); painter.drawText(QRect(15,170,150,300),Qt::AlignTop|Qt::AlignHCenter,tr("AETHER\n\nWelcome\n\nYour region\n\nStorage\n\nYour account\n\nReview\n\nInstall")); }
        setPixmap(QWizard::WatermarkPixmap,banner);
        auto welcome=page(tr("Make yourself at home"),tr("A modern desktop, built for Aether.")); auto wl=new QVBoxLayout(welcome);
        auto intro=new QLabel(tr("Set up your region, choose a disk, and create your account.\n\nYou can try the desktop before installing. No disk changes happen until you review your choices and confirm installation.\n\nThis preview installs to an entire disk. Manual partitioning and alongside-another-OS installation are not available yet.\n\nInstaller language: English")); intro->setWordWrap(true); wl->addWidget(intro); wl->addStretch();
        auto region=page(tr("Your region"),tr("These settings will apply to your installed desktop.")); auto rf=new QFormLayout(region);
        keyboard=new QComboBox; for(const auto &pair:QList<QPair<QString,QString>>{{"English (US)","us"},{"English (UK)","gb"},{"German","de"},{"French","fr"},{"Spanish","es"},{"Italian","it"},{"Portuguese","pt"},{"Portuguese (Brazil)","br"}}) keyboard->addItem(pair.first,pair.second);
        timezone=new QComboBox; timezone->addItem("UTC"); QFile zones("/usr/share/zoneinfo/zone.tab"); QStringList names;
        if(zones.open(QIODevice::ReadOnly)) for(const auto &line:zones.readAll().split('\n')) {if(line.startsWith('#')) continue;const auto fields=line.split('\t');if(fields.size()>2)names.append(QString::fromUtf8(fields[2]));}
        names.sort(); timezone->addItems(names); rf->addRow(tr("Keyboard layout"),keyboard); rf->addRow(tr("Time zone"),timezone);
        auto diskPage=page(tr("Choose storage"),tr("Only unmounted, writable whole disks of at least 16 GiB are listed.")); auto dl=new QVBoxLayout(diskPage);
        disks=new QComboBox; disks->setAccessibleName(tr("Installation disk")); dl->addWidget(disks); auto refresh=new QPushButton(tr("Refresh disks"));dl->addWidget(refresh);connect(refresh,&QPushButton::clicked,this,[this]{refreshDisks();});
        auto erase=new QLabel(tr("Erase disk and install Aether\n\nEvery partition and file on the selected disk will be removed. Other disks are left unchanged. Review the device name and size carefully."));erase->setWordWrap(true);dl->addWidget(erase);dl->addStretch();
        auto account=page(tr("Your account"),tr("Choose passwords of at least 12 characters. The live password will not be retained."));auto af=new QFormLayout(account);
        username=new QLineEdit("aether");username->setMaxLength(31);af->addRow(tr("Account name"),username);
        password=secret(af,tr("Account password"));repeatPassword=secret(af,tr("Confirm password"));
        encrypt=new QCheckBox(tr("Encrypt system storage (LUKS2)"));af->addRow(encrypt);
        auto secretPair=[af](const QString &label, QLineEdit *&first, QLineEdit *&second){auto row=new QWidget;auto layout=new QHBoxLayout(row);layout->setContentsMargins(0,0,0,0);first=new QLineEdit;second=new QLineEdit;for(auto entry:{first,second}){entry->setEchoMode(QLineEdit::Password);entry->setMaxLength(1024);entry->setInputMethodHints(Qt::ImhSensitiveData|Qt::ImhNoPredictiveText);layout->addWidget(entry);}first->setAccessibleName(label);second->setAccessibleName(label+QStringLiteral(" confirmation"));second->setPlaceholderText(QObject::tr("Confirm"));af->addRow(label,row);};
        secretPair(tr("Storage passphrase"),storage,repeatStorage);secretPair(tr("Recovery passphrase"),recovery,repeatRecovery);savedRecovery=new QCheckBox(tr("I saved the different recovery passphrase in a safe place"));af->addRow(savedRecovery);
        auto enable=[this](bool on){storage->setEnabled(on);recovery->setEnabled(on);repeatStorage->setEnabled(on);repeatRecovery->setEnabled(on);savedRecovery->setEnabled(on);}; connect(encrypt,&QCheckBox::toggled,this,enable);enable(false);
        backup=new QLineEdit;backup->setPlaceholderText(tr("Optional Linux path; configure encryption after installation"));af->addRow(tr("Backup destination"),backup);
        auto rp=page(tr("Ready to install?"),tr("Review these choices before making any disk changes."));auto rl=new QVBoxLayout(rp);review=new QLabel;review->setWordWrap(true);review->setTextFormat(Qt::PlainText);rl->addWidget(review);confirmation=new QLineEdit;confirmation->setAccessibleName(tr("Disk erase confirmation"));rl->addWidget(confirmation);rl->addStretch();
        auto ip=page(tr("Installing Aether"),tr("Keep this window open and the computer powered on."));auto il=new QVBoxLayout(ip);status=new QLabel;status->setWordWrap(true);il->addWidget(status);progress=new QProgressBar;il->addWidget(progress);details=new QTextEdit;details->setReadOnly(true);il->addWidget(details);
        connect(&process,&QProcess::readyReadStandardOutput,this,[this]{pending+=process.readAllStandardOutput();int end;while((end=pending.indexOf('\n'))>=0){const QByteArray line=pending.left(end);pending.remove(0,end+1);if(line.startsWith("AETHER_PROGRESS ")){const auto entry=QJsonDocument::fromJson(line.mid(16)).object();progress->setRange(0,7);progress->setValue(entry["step"].toInt());status->setText(entry["message"].toString());}else details->append(QString::fromUtf8(line).toHtmlEscaped());}});
        connect(&process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus state){running=false;progress->setRange(0,7);button(FinishButton)->setEnabled(true);button(CancelButton)->setEnabled(false);status->setText(code==0&&state==QProcess::NormalExit?tr("Aether is installed. Shut down, remove the ISO, then start your new system."):tr("Installation did not complete. Review the details below. Do not assume the disk is unchanged if installation had started."));});
    }
};
int main(int argc,char **argv){QApplication app(argc,argv);app.setApplicationName("Aether Installer");Installer window;window.show();return app.exec();}
