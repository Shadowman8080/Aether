// Aether's login interface. LightDM and PAM alone authenticate and start sessions.
#include <QApplication>
#include <QComboBox>
#include <QCheckBox>
#include <QDateTime>
#include <QDir>
#include <QFrame>
#include <QFile>
#include <QRegularExpression>
#include <QGuiApplication>
#include <QGraphicsEffect>
#include <QVariantAnimation>
#include <QInputDialog>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QMenu>
#include <QPainter>
#include <QPalette>
#include <QProcess>
#include <QPushButton>
#include <QQuickWidget>
#include <QScreen>
#include <QSvgRenderer>
#include <QTimer>
#include <QVBoxLayout>
#include <QLightDM/Greeter>
#include <QLightDM/Power>
#include <QLightDM/SessionsModel>

bool aetherCapsLockEnabled();

class ShakeEffect final : public QGraphicsEffect {
    qreal offset = 0;
public:
    using QGraphicsEffect::QGraphicsEffect;
    void setOffset(qreal value) { offset = value; update(); }
protected:
    QRectF boundingRectFor(const QRectF &rect) const override { return rect.adjusted(-16, 0, 16, 0); }
    void draw(QPainter *painter) override {
        QPoint origin;
        const QPixmap source = sourcePixmap(Qt::LogicalCoordinates, &origin, QGraphicsEffect::PadToEffectiveBoundingRect);
        painter->drawPixmap(QPointF(origin) + QPointF(offset, 0), source);
    }
};

// LightDM performs automatic login itself. Reporting the account lets the
// greeter stay out of the way instead of starting a competing PAM transaction
// that would cancel it and leave the seat at an empty password prompt.
QString autologinUser() {
    static const QRegularExpression re(
        QStringLiteral("^\\s*autologin-user\\s*=\\s*(\\S+)"),
        QRegularExpression::MultilineOption);
    QStringList paths{QStringLiteral("/etc/lightdm/lightdm.conf")};
    QDir drops(QStringLiteral("/etc/lightdm/lightdm.conf.d"));
    for (const QString &name : drops.entryList({QStringLiteral("*.conf")}, QDir::Files, QDir::Name))
        paths << drops.filePath(name);
    QString user;
    for (const QString &path : paths) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) continue;
        const auto found = re.match(QString::fromUtf8(file.readAll()));
        if (found.hasMatch()) user = found.captured(1);
    }
    return user;
}

// Present only where the sssd chain was built, so the greeter never offers a
// domain field on a system that cannot resolve one.
bool domainLoginAvailable() {
    return QFile::exists(QStringLiteral("/etc/aether/domain-login"));
}

// Local names stay restricted. Domain names arrive as user@domain or
// DOMAIN\user and are passed to LightDM unchanged for sssd to resolve.
bool acceptableUser(const QString &name) {
    if (name.isEmpty()) return false;
    static const QRegularExpression local(QStringLiteral("^[a-z][a-z0-9_-]{0,30}$"));
    static const QRegularExpression qualified(
        QStringLiteral("^[A-Za-z0-9._-]+(@[A-Za-z0-9.-]+|\\\\[A-Za-z0-9._-]+)$"));
    return local.match(name).hasMatch() || qualified.match(name).hasMatch();
}

class Login final : public QWidget {
    QLightDM::Greeter greeter;
    QLightDM::PowerInterface power;
    QSvgRenderer wallpaper{QStringLiteral("/usr/share/wallpapers/AetherAurora/contents/images/3840x2160.svg")};
    QLabel *clock, *user, *prompt, *message;
    QLineEdit *answer;
    // Only built when sssd is present, so a domain name can be typed directly.
    QLineEdit *usernameEdit = nullptr;
    QCheckBox *showPassword;
    QPushButton *submit;
    QQuickWidget *keyboard;
    QComboBox *session;
    QString username = QStringLiteral("aether"), pendingUser;
    bool waitingForAnswer = false;
    bool sessionChosen = false;
    void preferSession() {
        if (sessionChosen) return;
        QString key = greeter.defaultSessionHint();
        QFile vendor(QStringLiteral("/sys/class/dmi/id/sys_vendor"));
        if (vendor.open(QIODevice::ReadOnly) && vendor.readAll().contains("VMware"))
            key = QStringLiteral("plasmax11");
        const int preferred = session->findData(key, QLightDM::SessionsModel::KeyRole);
        if (preferred >= 0) session->setCurrentIndex(preferred);
    }
    QVariantAnimation *failureAnimation;
    void authenticate() {
        waitingForAnswer = false;
        showPassword->setChecked(false); showPassword->setEnabled(false);
        answer->clear(); answer->setEnabled(false); submit->setEnabled(false);
        if (usernameEdit) {
            const QString typed = usernameEdit->text().trimmed();
            if (!acceptableUser(typed)) {
                prompt->setText(tr("That user name is not valid here."));
                answer->setEnabled(true); submit->setEnabled(true);
                usernameEdit->setFocus();
                return;
            }
            username = typed;
        }
        user->setText(username); prompt->setText(tr("Signing in…"));
        greeter.authenticate(username);
    }
    void respond() {
        if (!waitingForAnswer || !greeter.inAuthentication()) return;
        QString response = answer->text();
        showPassword->setChecked(false); showPassword->setEnabled(false);
        answer->clear(); answer->setEnabled(false); submit->setEnabled(false);
        waitingForAnswer = false;
        greeter.respond(response);
        response.fill(QChar());
    }
protected:
    void paintEvent(QPaintEvent *) override {
        QPainter p(this); p.fillRect(rect(), QColor("#102033"));
        if (wallpaper.isValid()) {
            const QSizeF scaled = wallpaper.defaultSize().scaled(size(), Qt::KeepAspectRatioByExpanding);
            wallpaper.render(&p, QRectF((width()-scaled.width())/2, (height()-scaled.height())/2, scaled.width(), scaled.height()));
        }
        p.fillRect(rect(), QColor(0, 0, 0, 35));
    }
public:
    Login() {
        QFile defaultUser(QStringLiteral("/etc/aether/default-user"));
        if (defaultUser.open(QIODevice::ReadOnly)) {
            const auto configured = QString::fromUtf8(defaultUser.read(128)).trimmed();
            if (QRegularExpression(QStringLiteral("^[a-z][a-z0-9_-]{0,30}$")).match(configured).hasMatch()) username = configured;
        }
        setWindowTitle(tr("Aether Login"));
        setStyleSheet("QWidget { color: #f5f7fc; font-family: 'Noto Sans'; font-size: 16px; }"
          "QFrame#card { background: #152235; border: 1px solid #506078; border-radius: 24px; }"
          "QLabel { background: transparent; border: 0; }"
          "QLineEdit { background: #0b1422; border: 2px solid #71839b; border-radius: 10px; padding: 12px; selection-background-color: #88c9ff; selection-color: #07111e; }"
          "QLineEdit:focus { border-color: #88c9ff; }"
          "QComboBox { background: #0b1422; border: 2px solid #71839b; border-radius: 8px; padding: 7px; }"
          "QComboBox:focus { border-color: #b4dbff; }"
          "QPushButton { background: #293d58; border: 1px solid #71839b; border-radius: 10px; padding: 10px 18px; }"
          "QPushButton:focus { border: 2px solid #b4dbff; }"
          "QPushButton:hover { background: #3a5273; }"
          "QMenu { background: #152235; border: 1px solid #71839b; border-radius: 10px; padding: 8px; }"
          "QMenu::item { padding: 10px 24px; border-radius: 6px; }"
          "QMenu::item:selected { background: #3a5273; }"
          "QMenu::item:disabled { color: #aab4c3; }"
          "QPushButton:disabled { color: #aab4c3; background: #263140; }"
          "QPushButton#submit { background: #a8d4ff; color: #0b1422; font-weight: bold; }");
        auto outer = new QVBoxLayout(this); outer->setContentsMargins(32, 24, 32, 24);
        clock = new QLabel; clock->setAlignment(Qt::AlignCenter); outer->addWidget(clock);
        auto tick = [this] { clock->setText(QDateTime::currentDateTime().toString("dddd, MMMM d   •   h:mm AP")); };
        auto timer = new QTimer(this); connect(timer, &QTimer::timeout, this, tick); timer->start(1000); tick();
        outer->addStretch();
        auto card = new QFrame; card->setObjectName("card"); card->setFixedWidth(440);
        auto shake = new ShakeEffect(card); card->setGraphicsEffect(shake);
        failureAnimation = new QVariantAnimation(this);
        failureAnimation->setDuration(420);
        failureAnimation->setKeyValues({{0.0, 0.0}, {0.14, -12.0}, {0.28, 12.0},
            {0.42, -9.0}, {0.57, 9.0}, {0.71, -5.0}, {0.85, 5.0}, {1.0, 0.0}});
        connect(failureAnimation, &QVariantAnimation::valueChanged, this,
            [shake](const QVariant &value) { shake->setOffset(value.toReal()); });
        connect(failureAnimation, &QVariantAnimation::finished, this, [shake] { shake->setOffset(0); });
        auto form = new QVBoxLayout(card); form->setContentsMargins(32, 28, 32, 28); form->setSpacing(14);
        auto logo = new QLabel; QPixmap icon(64,64); icon.fill(Qt::transparent);
        { QPainter painter(&icon); QSvgRenderer svg(QStringLiteral("/usr/share/icons/hicolor/scalable/apps/aether-logo.svg")); svg.render(&painter); }
        logo->setPixmap(icon); logo->setAlignment(Qt::AlignCenter); form->addWidget(logo);
        auto title = new QLabel(tr("Welcome to Aether")); title->setStyleSheet("font-size: 27px; font-weight: 600;"); title->setAlignment(Qt::AlignCenter); form->addWidget(title);
        user = new QLabel(username); user->setAlignment(Qt::AlignCenter); form->addWidget(user);
        if (domainLoginAvailable()) {
            usernameEdit = new QLineEdit(username);
            usernameEdit->setAccessibleName(tr("User name"));
            usernameEdit->setPlaceholderText(tr("user, user@domain or DOMAIN\\user"));
            form->addWidget(usernameEdit);
            auto domainHint = new QLabel(tr("Add a domain to sign in with an Active Directory account."));
            domainHint->setWordWrap(true); form->addWidget(domainHint);
        }
        session = new QComboBox; session->setAccessibleName(tr("Desktop session"));
        session->setModel(new QLightDM::SessionsModel(QLightDM::SessionsModel::LocalSessions, session));
        connect(session, qOverload<int>(&QComboBox::activated), this, [this](int) { sessionChosen = true; });
        connect(session->model(), &QAbstractItemModel::rowsInserted, this, [this] { preferSession(); });
        connect(session->model(), &QAbstractItemModel::modelReset, this, [this] { preferSession(); });
        form->addWidget(session);
        message = new QLabel; message->setWordWrap(true); message->setTextFormat(Qt::PlainText); message->setAccessibleName(tr("Login status")); form->addWidget(message);
        prompt = new QLabel; prompt->setWordWrap(true); prompt->setTextFormat(Qt::PlainText); form->addWidget(prompt);
        answer = new QLineEdit; answer->setEchoMode(QLineEdit::Password); answer->setInputMethodHints(Qt::ImhSensitiveData | Qt::ImhNoPredictiveText); prompt->setBuddy(answer); form->addWidget(answer);
        showPassword = new QCheckBox(tr("Show password")); form->addWidget(showPassword);
        connect(showPassword, &QCheckBox::toggled, this, [this](bool visible) {
            answer->setEchoMode(visible ? QLineEdit::Normal : QLineEdit::Password);
            if (answer->isEnabled()) answer->setFocus();
        });
        auto keyStatus = new QLabel(tr("Passwords are case-sensitive."));
        keyStatus->setWordWrap(true); form->addWidget(keyStatus);
        auto keyTimer = new QTimer(this);
        connect(keyTimer, &QTimer::timeout, this, [keyStatus] {
            keyStatus->setText(aetherCapsLockEnabled()
                ? tr("Caps Lock is on. Passwords are case-sensitive.")
                : tr("Passwords are case-sensitive."));
        });
        keyTimer->start(250);
        submit = new QPushButton(tr("Continue")); submit->setObjectName("submit"); form->addWidget(submit);
        connect(submit, &QPushButton::clicked, this, [this] { respond(); });
        connect(answer, &QLineEdit::returnPressed, this, [this] { respond(); });
        auto other = new QPushButton(tr("Other user")); form->addWidget(other);
        connect(other, &QPushButton::clicked, this, [this] {
            bool ok=false; auto name=QInputDialog::getText(this,tr("Other user"),tr("Username"),QLineEdit::Normal,QString(),&ok).trimmed();
            if (!ok || !acceptableUser(name)) return;
            message->clear(); answer->clear(); pendingUser=name;
            if (greeter.inAuthentication()) greeter.cancelAuthentication();
            else { username=pendingUser; pendingUser.clear(); authenticate(); }
        });
        outer->addWidget(card, 0, Qt::AlignHCenter); outer->addStretch();
        auto controls = new QHBoxLayout;
        auto reader = new QPushButton(tr("Screen reader")); controls->addWidget(reader);
        connect(reader,&QPushButton::clicked,this,[this] {
            if (!QProcess::startDetached("/usr/bin/orca", {"--replace"})) message->setText(tr("The screen reader could not be started."));
        });
        auto keys = new QPushButton(tr("Keyboard")); keys->setCheckable(true); controls->addWidget(keys);
        controls->addStretch();
        auto powerButton = new QPushButton(tr("Power")); controls->addWidget(powerButton);
        powerButton->setAccessibleName(tr("Power menu"));
        auto powerMenu = new QMenu(powerButton);
        auto sleep = powerMenu->addAction(QIcon::fromTheme("system-suspend"), tr("Sleep"));
        powerMenu->addSeparator();
        auto restart = powerMenu->addAction(QIcon::fromTheme("system-reboot"), tr("Restart"));
        auto shutdown = powerMenu->addAction(QIcon::fromTheme("system-shutdown"), tr("Shut Down"));
        powerButton->setMenu(powerMenu);
        connect(powerMenu, &QMenu::aboutToShow, this, [this, sleep, restart, shutdown] {
            sleep->setEnabled(power.canSuspend());
            restart->setEnabled(power.canRestart());
            shutdown->setEnabled(power.canShutdown());
        });
        connect(sleep, &QAction::triggered, this, [this] {
            answer->clear();
            if (!power.suspend()) message->setText(tr("Sleep is not available on this computer."));
        });
        connect(restart,&QAction::triggered,this,[this] {
            if (QMessageBox::question(this,tr("Restart Aether"),tr("Restart this computer?"),QMessageBox::Yes|QMessageBox::No,QMessageBox::No)==QMessageBox::Yes && !power.restart()) message->setText(tr("Restart is not available."));
        });
        connect(shutdown,&QAction::triggered,this,[this] {
            if (QMessageBox::question(this,tr("Shut down Aether"),tr("Shut down this computer?"),QMessageBox::Yes|QMessageBox::No,QMessageBox::No)==QMessageBox::Yes && !power.shutdown()) message->setText(tr("Shutdown is not available."));
        });
        outer->addLayout(controls);
        keyboard = new QQuickWidget; keyboard->setResizeMode(QQuickWidget::SizeRootObjectToView); keyboard->setFixedHeight(220); keyboard->setSource(QUrl::fromLocalFile("/usr/share/aether/greeter/Keyboard.qml")); keyboard->hide(); outer->addWidget(keyboard);
        connect(keys,&QPushButton::toggled,this,[this,logo,title,other](bool on) {
            // Keep the PAM prompt and entry visible on smaller displays.
            logo->setVisible(!on); title->setVisible(!on); other->setVisible(!on);
            clock->setVisible(!on); session->setVisible(!on);
            keyboard->setVisible(on); answer->setFocus();
        });
        connect(&greeter,&QLightDM::Greeter::showPrompt,this,[this](const QString &text, QLightDM::Greeter::PromptType type) {
            prompt->setText(text); answer->setAccessibleName(text); answer->clear();
            showPassword->setChecked(false);
            showPassword->setEnabled(type==QLightDM::Greeter::PromptTypeSecret);
            answer->setEchoMode(type==QLightDM::Greeter::PromptTypeSecret ? QLineEdit::Password : QLineEdit::Normal);
            waitingForAnswer=true; answer->setEnabled(true); submit->setEnabled(true); answer->setFocus();
        });
        connect(&greeter,&QLightDM::Greeter::showMessage,this,[this](const QString &text, QLightDM::Greeter::MessageType) { message->setText(text); });
        connect(&greeter,&QLightDM::Greeter::authenticationComplete,this,[this] {
            answer->clear(); waitingForAnswer=false;
            if (!pendingUser.isEmpty()) { username=pendingUser; pendingUser.clear(); authenticate(); return; }
            if (!greeter.isAuthenticated()) {
                message->setText(tr("Sign-in failed. Check your password and try again."));
                failureAnimation->stop(); failureAnimation->start();
                authenticate(); return;
            }
            prompt->setText(tr("Starting your desktop…")); answer->setEnabled(false); submit->setEnabled(false);
            const QString selected = session->currentData(QLightDM::SessionsModel::KeyRole).toString();
            if (!greeter.startSessionSync(selected.isEmpty() ? greeter.defaultSessionHint() : selected)) {
                message->setText(tr("The desktop could not start. Please try again.")); authenticate();
            }
        });
        QTimer::singleShot(0,this,[this] {
            if (!greeter.connectToDaemonSync()) { message->setText(tr("Cannot connect to the login service.")); answer->setEnabled(false); submit->setEnabled(false); return; }
            preferSession();
            const QString automatic = autologinUser();
            if (!automatic.isEmpty() && automatic == username) {
                // LightDM signs this account in itself. Starting a PAM
                // transaction here would cancel that and strand the seat at an
                // empty password prompt.
                prompt->setText(tr("Signing in automatically…"));
                answer->setEnabled(false); submit->setEnabled(false);
                return;
            }
            authenticate();
        });
    }
};
int main(int argc, char **argv) {
    qputenv("QT_IM_MODULE", "qtvirtualkeyboard");
    QApplication app(argc, argv);
    QApplication::setApplicationName("Aether Login");
    QPalette palette;
    palette.setColor(QPalette::Window, QColor("#152235"));
    palette.setColor(QPalette::WindowText, QColor("#f5f7fc"));
    palette.setColor(QPalette::Base, QColor("#0b1422"));
    palette.setColor(QPalette::Text, QColor("#f5f7fc"));
    palette.setColor(QPalette::Button, QColor("#293d58"));
    palette.setColor(QPalette::ButtonText, QColor("#f5f7fc"));
    palette.setColor(QPalette::Highlight, QColor("#a8d4ff"));
    palette.setColor(QPalette::HighlightedText, QColor("#0b1422"));
    app.setPalette(palette);
    Login login; login.resize(QGuiApplication::primaryScreen()->size()); login.showFullScreen();
    return app.exec();
}
