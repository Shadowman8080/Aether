#include <QApplication>
#include <QFrame>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QMainWindow>
#include <QProcess>
#include <QPushButton>
#include <QScrollArea>
#include <QStatusBar>
#include <QVBoxLayout>

class SecurityCenter : public QMainWindow {
    QProcess process;
    QVBoxLayout *cards;
    QPushButton *refresh;
    QPushButton *protectedCheck;
public:
    SecurityCenter() {
        setWindowTitle("Aether Security");
        resize(860, 700);
        auto *body = new QWidget;
        auto *layout = new QVBoxLayout(body);
        layout->setContentsMargins(26, 22, 26, 20);
        layout->setSpacing(14);
        auto *heading = new QLabel("Security & privacy");
        QFont font = heading->font(); font.setPointSize(24); font.setBold(true); heading->setFont(font);
        layout->addWidget(heading);
        auto *intro = new QLabel("See what is working, what needs setup, and what this development build does not yet protect.");
        intro->setWordWrap(true); layout->addWidget(intro);
        auto *buttons = new QHBoxLayout;
        refresh = new QPushButton("&Refresh");
        protectedCheck = new QPushButton("&Check protected settings…");
        auto *backup = new QPushButton("Set up encrypted &backups…");
        buttons->addWidget(refresh); buttons->addWidget(protectedCheck); buttons->addStretch(); buttons->addWidget(backup);
        layout->addLayout(buttons);
        auto *scroll = new QScrollArea;
        scroll->setWidgetResizable(true);
        scroll->setFrameShape(QFrame::NoFrame);
        auto *contents = new QWidget;
        cards = new QVBoxLayout(contents); cards->setContentsMargins(0, 0, 8, 0); cards->setSpacing(10);
        scroll->setWidget(contents); layout->addWidget(scroll);
        setCentralWidget(body);
        connect(refresh, &QPushButton::clicked, this, [this] { inspect(false); });
        connect(protectedCheck, &QPushButton::clicked, this, [this] { inspect(true); });
        connect(backup, &QPushButton::clicked, this, [] {
            QProcess::startDetached("/usr/bin/konsole", {"--hold", "-e", "/usr/bin/sudo", "/usr/bin/aether-backup", "setup"});
        });
        connect(&process, &QProcess::finished, this, [this](int code, QProcess::ExitStatus status) {
            refresh->setEnabled(true); protectedCheck->setEnabled(true);
            if (code != 0 || status != QProcess::NormalExit) {
                statusBar()->showMessage("The check could not finish or authorization was cancelled. Existing results are unchanged.");
                return;
            }
            QJsonParseError error;
            auto doc = QJsonDocument::fromJson(process.readAllStandardOutput(), &error);
            if (error.error != QJsonParseError::NoError || !doc.isArray()) {
                statusBar()->showMessage("The status tool returned an invalid response. No protection state was inferred.");
                return;
            }
            while (auto *item = cards->takeAt(0)) { delete item->widget(); delete item; }
            for (auto value : doc.array()) {
                const auto row = value.toObject();
                auto *card = new QFrame;
                card->setFrameShape(QFrame::StyledPanel);
                auto *inside = new QVBoxLayout(card); inside->setContentsMargins(15, 12, 15, 12);
                auto *top = new QHBoxLayout;
                auto *title = new QLabel(row["control"].toString());
                title->setTextFormat(Qt::PlainText);
                QFont titleFont = title->font(); titleFont.setBold(true); title->setFont(titleFont);
                const QString state = row["state"].toString();
                auto *badge = new QLabel(state);
                badge->setTextFormat(Qt::PlainText);
                badge->setAccessibleName("Protection state: " + state);
                const bool verified = state == "enforced" || state == "enabled" || state == "none reported";
                badge->setStyleSheet(verified ? "color:#167344; font-weight:600;" : "color:#a56613; font-weight:600;");
                top->addWidget(title); top->addStretch(); top->addWidget(badge); inside->addLayout(top);
                auto *detail = new QLabel(row["detail"].toString());
                detail->setTextFormat(Qt::PlainText); detail->setWordWrap(true);
                detail->setTextInteractionFlags(Qt::TextSelectableByMouse | Qt::TextSelectableByKeyboard);
                inside->addWidget(detail); cards->addWidget(card);
            }
            cards->addStretch();
            statusBar()->showMessage("Observed status, not a security score. A configured feature may still need end-to-end testing.");
        });
        connect(&process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
            refresh->setEnabled(true); protectedCheck->setEnabled(true);
            statusBar()->showMessage("The security status tool could not be started.");
        });
        inspect(false);
    }
    void inspect(bool privileged) {
        if (process.state() != QProcess::NotRunning) return;
        refresh->setEnabled(false); protectedCheck->setEnabled(false);
        statusBar()->showMessage(privileged ? "Authorizing a read-only check of firewall and confinement settings…" : "Reading current protection state…");
        if (privileged)
            process.start("/usr/bin/pkexec", {"/usr/libexec/aether-security-read-status"});
        else
            process.start("/usr/bin/aether-security-status", {});
    }
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.setApplicationName("Aether Security");
    SecurityCenter window; window.show();
    return app.exec();
}
