#include <QtWidgets>

class Assistant : public QMainWindow {
    QTextBrowser *conversation;
    QPlainTextEdit *input;
    QLabel *status;
    QPushButton *send, *download;
    QProcess backend, transfer;
    QByteArray backendBuffer, transferBuffer;
    bool busy = false;
    bool modelInstalled = false;

    void showMessage(const QString &speaker, const QString &text) {
        conversation->append("<p><b>"+speaker.toHtmlEscaped()+"</b><br>"+
            text.toHtmlEscaped().replace("\n", "<br>")+"</p>");
        conversation->verticalScrollBar()->setValue(conversation->verticalScrollBar()->maximum());
    }
    void setBusy(bool value) {
        busy = value; send->setEnabled(modelInstalled && !busy);
    }
    void readLines(QProcess &process, QByteArray &buffer, bool downloading) {
        buffer += process.readAllStandardOutput();
        while (buffer.contains('\n')) {
            int at = buffer.indexOf('\n');
            auto doc = QJsonDocument::fromJson(buffer.left(at));
            buffer.remove(0, at+1);
            if (!doc.isObject()) continue;
            auto object = doc.object();
            auto type = object["type"].toString();
            if (type == "answer") {
                showMessage("Aether", object["text"].toString());
                status->setText("Local · Conversation stays in this window"); setBusy(false);
            } else if (type == "model_invalid") {
                modelInstalled = false; download->show(); setBusy(false);
            } else if (type == "error") {
                showMessage("Notice", object["message"].toString());
                status->setText("Something needs attention"); setBusy(false);
            } else if (type == "status") {
                status->setText(object["message"].toString());
            } else if (type == "progress" && downloading) {
                auto total = object["total"].toDouble();
                auto received = object["received"].toDouble();
                status->setText(QString("Downloading local model · %1%").arg(total > 0 ? int(100*received/total) : 0));
            } else if (type == "downloaded") {
                modelInstalled = true; download->hide(); setBusy(false);
                status->setText("Local model ready · Ask a question");
            }
        }
    }
    void ensureBackend() {
        if (backend.state() != QProcess::NotRunning) return;
        backendBuffer.clear();
        backend.start("aether-ai", {"session"});
    }
    void ask() {
        auto text = input->toPlainText().trimmed();
        if (busy || !modelInstalled || text.isEmpty()) return;
        if (text.size() > 6000) {
            QMessageBox::information(this, "Message length", "Please keep each message under 6,000 characters."); return;
        }
        ensureBackend();
        if (!backend.waitForStarted(3000)) {
            showMessage("Notice", "The assistant service could not start."); return;
        }
        showMessage("You", text); input->clear(); setBusy(true);
        backend.write(QJsonDocument(QJsonObject{{"text", text}}).toJson(QJsonDocument::Compact)+'\n');
    }
public:
    Assistant() {
        setWindowTitle("Aether Assistant"); resize(760, 680);
        setWindowIcon(QIcon::fromTheme("aether-assistant"));
        auto *central = new QWidget;
        auto *layout = new QVBoxLayout(central); layout->setContentsMargins(24,20,24,20); layout->setSpacing(12);
        auto *heading = new QLabel("Aether Assistant");
        auto font = heading->font(); font.setPointSize(22); font.setBold(true); heading->setFont(font);
        layout->addWidget(heading);
        auto *description = new QLabel("Ask about Linux, explain an error, or work on text you share.");
        description->setWordWrap(true); layout->addWidget(description);
        conversation = new QTextBrowser;
        conversation->setOpenExternalLinks(false); conversation->setOpenLinks(false);
        conversation->setFrameShape(QFrame::NoFrame); layout->addWidget(conversation, 1);
        showMessage("Welcome", "Answers run on this computer. I can suggest steps, but cannot execute commands or read your files. Answers may be mistaken; review commands before using them.");
        input = new QPlainTextEdit; input->setPlaceholderText("Ask a question or paste text…"); input->setMaximumHeight(130);
        layout->addWidget(input);
        auto *row = new QHBoxLayout;
        auto *attach = new QPushButton("Add text file"); row->addWidget(attach);
        auto *clear = new QPushButton("New conversation"); row->addWidget(clear);
        row->addStretch();
        download = new QPushButton("Download local model"); row->addWidget(download);
        send = new QPushButton("Send"); send->setDefault(true); send->setEnabled(false); row->addWidget(send);
        layout->addLayout(row);
        status = new QLabel("Checking local model…"); status->setWordWrap(true); layout->addWidget(status);
        setCentralWidget(central);
        connect(send, &QPushButton::clicked, this, [this]{ask();});
        auto *shortcut = new QShortcut(QKeySequence("Ctrl+Return"), this);
        connect(shortcut, &QShortcut::activated, this, [this]{ask();});
        connect(attach, &QPushButton::clicked, this, [this]{
            auto name = QFileDialog::getOpenFileName(this, "Choose text to share", {}, "Text files (*.txt *.log *.md);;All files (*)");
            if (name.isEmpty()) return;
            QFile file(name);
            if (!file.open(QIODevice::ReadOnly) || file.size() > 16000) {
                QMessageBox::information(this, "Text file", "Choose a readable text file under 16 KB."); return;
            }
            auto text = QString::fromUtf8(file.readAll());
            input->setPlainText("Please help me understand this text:\n\n"+text);
            status->setText("Review the text above, then press Send to share it with the local model.");
        });
        connect(clear, &QPushButton::clicked, this, [this]{
            backend.terminate(); if (!backend.waitForFinished(6000)) backend.kill();
            conversation->clear(); input->clear(); setBusy(false);
            status->setText("New conversation · Model starts when you send a message");
        });
        connect(&backend, &QProcess::readyReadStandardOutput, this, [this]{readLines(backend, backendBuffer, false);});
        connect(&backend, &QProcess::errorOccurred, this, [this](QProcess::ProcessError){
            status->setText("The local assistant service is unavailable."); setBusy(false);
        });
        connect(&backend, &QProcess::finished, this, [this](int, QProcess::ExitStatus){
            if (busy) { status->setText("The local session stopped. You can try again."); setBusy(false); }
        });
        connect(download, &QPushButton::clicked, this, [this]{
            if (QMessageBox::question(this, "Download local model", "Download the 563 MB Qwen3.5 0.8B model from Hugging Face? It uses the Apache-2.0 license. After downloading, chat works offline.") != QMessageBox::Yes) return;
            download->setEnabled(false); transferBuffer.clear();
            transfer.start("aether-ai", {"download"});
        });
        connect(&transfer, &QProcess::readyReadStandardOutput, this, [this]{readLines(transfer, transferBuffer, true);});
        connect(&transfer, &QProcess::finished, this, [this](int code, QProcess::ExitStatus){
            download->setEnabled(true); if (code && !modelInstalled) status->setText("Download did not finish. You can retry.");
        });
        connect(&transfer, &QProcess::errorOccurred, this, [this](QProcess::ProcessError){
            download->setEnabled(true); status->setText("Could not start the model downloader.");
        });
        auto *probe = new QProcess(this);
        connect(probe, &QProcess::errorOccurred, this, [this, probe](QProcess::ProcessError){
            status->setText("The assistant service is missing. Check the Aether Assistant installation.");
            send->setEnabled(false); download->setEnabled(false); probe->deleteLater();
        });
        connect(probe, &QProcess::finished, this, [this, probe](int code, QProcess::ExitStatus){
            auto object = QJsonDocument::fromJson(probe->readAllStandardOutput()).object();
            modelInstalled = code == 0 && object["installed"].toBool();
            download->setVisible(!modelInstalled); setBusy(false);
            status->setText(modelInstalled ? "Local model ready · Starts when needed" : "Download the optional model to enable offline chat.");
            probe->deleteLater();
        });
        probe->start("aether-ai", {"status"});
    }
    ~Assistant() override {
        backend.terminate(); if (!backend.waitForFinished(6000)) { backend.kill(); backend.waitForFinished(); }
        transfer.terminate(); if (!transfer.waitForFinished(2000)) { transfer.kill(); transfer.waitForFinished(); }
    }
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    app.setApplicationName("aether-assistant"); app.setOrganizationName("Aether");
    Assistant window; window.show();
    const auto args = app.arguments();
    const auto screenshot = args.indexOf("--screenshot");
    if (screenshot >= 0 && screenshot+1 < args.size()) {
        QTimer::singleShot(800, &app, [&]{
            const bool saved = window.grab().save(args.at(screenshot+1));
            app.exit(saved ? 0 : 1);
        });
    }
    return app.exec();
}
