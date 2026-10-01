// SPDX-License-Identifier: GPL-2.0-or-later
#include <QApplication>
#include <QActionGroup>
#include <QCollator>
#include <QComboBox>
#include <QDesktopServices>
#include <QDir>
#include <QFileInfo>
#include <QFileSystemModel>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMainWindow>
#include <QMessageBox>
#include <QSettings>
#include <QSet>
#include <QShortcut>
#include <QSortFilterProxyModel>
#include <QSplitter>
#include <QStackedWidget>
#include <QStandardPaths>
#include <QStatusBar>
#include <QTextStream>
#include <QToolBar>
#include <QTreeView>
#include <QVBoxLayout>
#include <KService>
#include <KIO/ApplicationLauncherJob>
#include <algorithm>

struct Application {
    KService::Ptr service;
    QString name, description, id;
    QStringList categories;
};

class FileFilter : public QSortFilterProxyModel {
public:
    using QSortFilterProxyModel::QSortFilterProxyModel;
    QString folder;
protected:
    bool filterAcceptsRow(int row, const QModelIndex &parent) const override {
        auto *model = static_cast<QFileSystemModel *>(sourceModel());
        const auto path = model->filePath(model->index(row, 0, parent));
        // Keep the root and its ancestors mapped while filtering its children.
        if (path == folder || folder.startsWith(path.endsWith('/') ? path : path + '/')) return true;
        return QSortFilterProxyModel::filterAcceptsRow(row, parent);
    }
};

static QList<Application> applications()
{
    QList<Application> result;
    QSet<QString> seen;
    for (const auto &service : KService::allServices()) {
        if (!service->isApplication() || service->noDisplay() || !service->showInCurrentDesktop()) continue;
        const auto id = service->desktopEntryName();
        if (seen.contains(id) || service->name().isEmpty()) continue;
        seen.insert(id);
        result.append({service, service->name(), service->genericName(), id, service->categories()});
    }
    QCollator collator;
    collator.setCaseSensitivity(Qt::CaseInsensitive);
    collator.setNumericMode(true);
    std::sort(result.begin(), result.end(), [&collator](const auto &a, const auto &b) {
        const int comparison = collator.compare(a.name, b.name);
        return comparison == 0 ? a.id < b.id : comparison < 0;
    });
    return result;
}

class VectorWindow : public QMainWindow {
public:
    VectorWindow() : catalog(applications())
    {
        setWindowTitle(tr("Applications — Vector"));
        setWindowIcon(QIcon::fromTheme("org.aether.Vector"));
        resize(1040, 690);
        auto *toolbar = addToolBar(tr("Navigation"));
        toolbar->setMovable(false);
        toolbar->setIconSize(QSize(20, 20));
        back = toolbar->addAction(QIcon::fromTheme("go-previous"), tr("Back"), this, [this] { travel(-1); });
        forward = toolbar->addAction(QIcon::fromTheme("go-next"), tr("Forward"), this, [this] { travel(1); });
        auto *up = toolbar->addAction(QIcon::fromTheme("go-up"), tr("Enclosing Folder"), this, [this] {
            if (current != "applications:") navigate(QFileInfo(current).dir().absolutePath());
        });
        back->setShortcut(QKeySequence("Alt+Left"));
        forward->setShortcut(QKeySequence("Alt+Right"));
        up->setShortcut(QKeySequence("Alt+Up"));
        toolbar->addSeparator();
        location = new QLineEdit;
        location->setAccessibleName(tr("Location"));
        location->setMinimumWidth(180);
        toolbar->addWidget(location);
        connect(location, &QLineEdit::returnPressed, this, [this] {
            auto text = location->text().trimmed();
            if (text == tr("Applications") || text == "applications:") navigate("applications:");
            else {
                if (text == "~") text = QDir::homePath();
                if (text.startsWith("~/")) text.replace(0, 1, QDir::homePath());
                navigate(text);
            }
        });
        auto *viewModes = new QActionGroup(this);
        for (const auto &mode : {QString("Icons"), QString("List")}) {
            auto *action = toolbar->addAction(QIcon::fromTheme(mode == "Icons" ? "view-grid" : "view-list-details"), mode);
            action->setCheckable(true);
            action->setChecked(mode == "Icons");
            viewModes->addAction(action);
            action->setShortcut(QKeySequence(mode == "Icons" ? "Ctrl+1" : "Ctrl+2"));
            connect(action, &QAction::triggered, this, [this, mode] { icons = mode == "Icons"; updateView(); });
        }
        search = new QLineEdit;
        search->setClearButtonEnabled(true);
        search->setPlaceholderText(tr("Search applications"));
        search->setAccessibleName(tr("Search current view"));
        search->setMaximumWidth(260);
        toolbar->addWidget(search);
        connect(search, &QLineEdit::textChanged, this, [this] {
            if (current == "applications:") filterApplications();
            else proxy->setFilterFixedString(search->text());
        });
        connect(search, &QLineEdit::returnPressed, this, [this] {
            if (current == "applications:" && appList->count() > 0) {
                appList->setCurrentRow(0);
                appList->setFocus();
            }
        });
        connect(new QShortcut(QKeySequence::Find, this), &QShortcut::activated, search, qOverload<>(&QWidget::setFocus));
        connect(new QShortcut(QKeySequence("Ctrl+L"), this), &QShortcut::activated, this, [this] { location->setFocus(); location->selectAll(); });
        auto *refresh = new QShortcut(QKeySequence::Refresh, this);
        connect(refresh, &QShortcut::activated, this, [this] { catalog = applications(); filterApplications(); });

        auto *splitter = new QSplitter;
        splitter->setChildrenCollapsible(false);
        setCentralWidget(splitter);
        sidebar = new QListWidget;
        sidebar->setAccessibleName(tr("Places"));
        sidebar->setIconSize(QSize(22, 22));
        sidebar->setSpacing(4);
        sidebar->setMinimumWidth(170);
        sidebar->setMaximumWidth(300);
        auto *heading = new QListWidgetItem(tr("FAVORITES"), sidebar);
        heading->setFlags(Qt::NoItemFlags);
        addPlace(tr("Applications"), "applications:", "applications-all");
        addPlace(tr("Home"), QDir::homePath(), "user-home");
        addFolder(tr("Desktop"), QStandardPaths::DesktopLocation, "user-desktop");
        addFolder(tr("Documents"), QStandardPaths::DocumentsLocation, "folder-documents");
        addFolder(tr("Downloads"), QStandardPaths::DownloadLocation, "folder-download");
        addFolder(tr("Pictures"), QStandardPaths::PicturesLocation, "folder-pictures");
        addFolder(tr("Music"), QStandardPaths::MusicLocation, "folder-music");
        addFolder(tr("Videos"), QStandardPaths::MoviesLocation, "folder-videos");
        splitter->addWidget(sidebar);
        connect(sidebar, &QListWidget::itemClicked, this, [this](QListWidgetItem *item) {
            if (!item->data(Qt::UserRole).toString().isEmpty()) navigate(item->data(Qt::UserRole).toString());
        });
        auto *content = new QWidget;
        auto *layout = new QVBoxLayout(content);
        layout->setContentsMargins(24, 18, 24, 12);
        auto *header = new QHBoxLayout;
        title = new QLabel;
        auto font = title->font(); font.setPointSize(font.pointSize() + 7); font.setBold(true); title->setFont(font);
        header->addWidget(title, 1);
        categories = new QComboBox;
        categories->setAccessibleName(tr("Application category"));
        categories->addItem(tr("All Applications"), "");
        for (const auto &pair : QList<QPair<QString, QString>>{
             {tr("Accessories"), "Utility"}, {tr("Development"), "Development"}, {tr("Education"), "Education"},
             {tr("Games"), "Game"}, {tr("Graphics"), "Graphics"}, {tr("Internet"), "Network"},
             {tr("Office"), "Office"}, {tr("Science"), "Science"}, {tr("Sound & Video"), "AudioVideo"},
             {tr("Settings"), "Settings"}, {tr("System"), "System"}}) categories->addItem(pair.first, pair.second);
        header->addWidget(categories);
        layout->addLayout(header);
        connect(categories, &QComboBox::currentIndexChanged, this, [this] { filterApplications(); });
        pages = new QStackedWidget;
        appList = new QListWidget;
        appList->setAccessibleName(tr("Applications, sorted by name"));
        appList->setResizeMode(QListView::Adjust);
        appList->setMovement(QListView::Static);
        appList->setWordWrap(true);
        appList->setTextElideMode(Qt::ElideNone);
        appList->setUniformItemSizes(true);
        appList->setFrameShape(QFrame::NoFrame);
        pages->addWidget(appList);
        connect(appList, &QListWidget::itemActivated, this, [this](QListWidgetItem *item) {
            const auto index = item->data(Qt::UserRole).toInt();
            if (index < 0 || index >= catalog.size()) return;
            auto *job = new KIO::ApplicationLauncherJob(catalog[index].service, this);
            connect(job, &KJob::result, this, [this](KJob *finished) {
                if (finished->error()) QMessageBox::warning(this, tr("Could not open application"), finished->errorString());
            });
            job->start();
        });
        files = new QFileSystemModel(this);
        files->setReadOnly(true);
        files->setFilter(QDir::AllEntries | QDir::NoDotAndDotDot | QDir::AllDirs);
        files->setRootPath(QDir::rootPath());
        proxy = new FileFilter(this);
        proxy->setSourceModel(files);
        proxy->setFilterCaseSensitivity(Qt::CaseInsensitive);
        proxy->setFilterKeyColumn(0);
        fileIcons = new QListView;
        fileIcons->setModel(proxy);
        fileIcons->setViewMode(QListView::IconMode);
        fileIcons->setMovement(QListView::Static);
        fileIcons->setResizeMode(QListView::Adjust);
        fileIcons->setIconSize(QSize(56, 56));
        fileIcons->setGridSize(QSize(130, 104));
        fileIcons->setWordWrap(true);
        fileIcons->setEditTriggers(QAbstractItemView::NoEditTriggers);
        fileIcons->setAccessibleName(tr("Files"));
        pages->addWidget(fileIcons);
        fileDetails = new QTreeView;
        fileDetails->setModel(proxy);
        fileDetails->setRootIsDecorated(false);
        fileDetails->setItemsExpandable(false);
        fileDetails->setSortingEnabled(true);
        fileDetails->sortByColumn(0, Qt::AscendingOrder);
        fileDetails->setEditTriggers(QAbstractItemView::NoEditTriggers);
        fileDetails->setAccessibleName(tr("File details"));
        pages->addWidget(fileDetails);
        auto openFile = [this](const QModelIndex &index) {
            const auto path = files->filePath(proxy->mapToSource(index));
            if (QFileInfo(path).isDir()) navigate(path);
            else if (!QDesktopServices::openUrl(QUrl::fromLocalFile(path)))
                QMessageBox::warning(this, tr("Could not open file"), tr("No application could open this file."));
        };
        connect(fileIcons, &QListView::activated, this, openFile);
        connect(fileDetails, &QTreeView::activated, this, openFile);
        layout->addWidget(pages, 1);
        empty = new QLabel(tr("No applications match your search."));
        empty->setAlignment(Qt::AlignCenter);
        layout->addWidget(empty);
        splitter->addWidget(content);
        splitter->setSizes({210, 830});
        navigate("applications:");
    }

    bool smokeTest()
    {
        const int all = appList->count();
        search->setText("aether-vector-no-match-328572");
        const bool filtered = appList->count() == 0 && !empty->isHidden();
        search->clear();
        const bool restored = appList->count() == all;
        navigate(QDir::homePath());
        const bool home = current == QDir::homePath() && pages->currentWidget() == fileIcons;
        travel(-1);
        const bool historyWorks = current == "applications:";
        return all > 0 && filtered && restored && home && historyWorks;
    }

private:
    QList<Application> catalog;
    QListWidget *sidebar, *appList;
    QListView *fileIcons;
    QTreeView *fileDetails;
    QFileSystemModel *files;
    FileFilter *proxy;
    QLineEdit *search, *location;
    QComboBox *categories;
    QLabel *title, *empty;
    QStackedWidget *pages;
    QAction *back, *forward;
    QString current;
    QStringList history;
    int historyIndex = -1;
    bool icons = true;

    void addPlace(const QString &name, const QString &path, const QString &icon) {
        auto *item = new QListWidgetItem(QIcon::fromTheme(icon), name, sidebar);
        item->setData(Qt::UserRole, path);
    }
    void addFolder(const QString &name, QStandardPaths::StandardLocation type, const QString &icon) {
        const auto path = QStandardPaths::writableLocation(type);
        if (!path.isEmpty()) addPlace(name, path, icon);
    }
    void travel(int delta) {
        const int next = historyIndex + delta;
        if (next < 0 || next >= history.size()) return;
        historyIndex = next;
        navigate(history[next], false);
    }
    void navigate(QString path, bool remember = true) {
        if (path != "applications:") {
            QFileInfo info(path);
            if (!info.isDir() || !info.isReadable()) {
                QMessageBox::information(this, tr("Folder unavailable"), tr("This folder does not exist or cannot be read."));
                location->setText(current);
                return;
            }
            path = QDir(path).absolutePath();
        }
        current = path;
        if (remember && (historyIndex < 0 || history[historyIndex] != path)) {
            history = history.mid(0, historyIndex + 1); history.append(path); historyIndex = history.size() - 1;
        }
        search->clear();
        back->setEnabled(historyIndex > 0); forward->setEnabled(historyIndex + 1 < history.size());
        const bool apps = path == "applications:";
        title->setText(apps ? tr("Applications") : (QFileInfo(path).fileName().isEmpty() ? path : QFileInfo(path).fileName()));
        setWindowTitle(title->text() + tr(" — Vector"));
        location->setText(apps ? tr("Applications") : path);
        search->setPlaceholderText(apps ? tr("Search applications") : tr("Search this folder"));
        categories->setVisible(apps);
        for (int i = 0; i < sidebar->count(); ++i) sidebar->item(i)->setSelected(sidebar->item(i)->data(Qt::UserRole).toString() == path);
        if (!apps) {
            proxy->folder = path;
            proxy->setFilterFixedString("");
            auto index = proxy->mapFromSource(files->index(path));
            fileIcons->setRootIndex(index); fileDetails->setRootIndex(index);
            fileDetails->setColumnWidth(0, 360);
        }
        updateView();
    }
    void updateView() {
        if (current == "applications:") {
            pages->setCurrentWidget(appList);
            appList->setViewMode(icons ? QListView::IconMode : QListView::ListMode);
            appList->setIconSize(icons ? QSize(56, 56) : QSize(28, 28));
            appList->setGridSize(icons ? QSize(144, 112) : QSize());
            appList->setSpacing(icons ? 8 : 4);
            filterApplications();
        } else {
            pages->setCurrentWidget(icons ? static_cast<QWidget *>(fileIcons) : static_cast<QWidget *>(fileDetails));
            empty->hide(); statusBar()->showMessage(current);
        }
    }
    void filterApplications() {
        appList->clear();
        const auto term = search->text().trimmed();
        const auto category = categories->currentData().toString();
        for (int i = 0; i < catalog.size(); ++i) {
            const auto &app = catalog[i];
            if (!category.isEmpty() && !app.categories.contains(category)) continue;
            if (!(app.name + " " + app.description).contains(term, Qt::CaseInsensitive)) continue;
            auto *item = new QListWidgetItem(QIcon::fromTheme(app.service->icon(), QIcon::fromTheme("application-x-executable")), app.name, appList);
            if (icons) item->setSizeHint(QSize(136, 108));
            item->setData(Qt::UserRole, i);
            item->setToolTip(app.description.isEmpty() ? app.name : app.name + "\n" + app.description);
        }
        if (current == "applications:") {
            empty->setVisible(appList->count() == 0);
            statusBar()->showMessage(tr("%1 applications · Sorted by name").arg(appList->count()));
        }
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setApplicationName("Vector");
    app.setOrganizationName("Aether");
    app.setDesktopFileName("org.aether.Vector");
    if (app.arguments().contains("--dump-applications")) {
        QJsonArray entries;
        for (const auto &item : applications()) entries.append(QJsonObject{{"name", item.name}, {"id", item.id}, {"categories", QJsonArray::fromStringList(item.categories)}});
        QTextStream(stdout) << QJsonDocument(entries).toJson();
        return 0;
    }
    VectorWindow window;
    if (app.arguments().contains("--self-test")) {
        const bool passed = window.smokeTest();
        QTextStream(stdout) << (passed ? "VECTOR_SMOKE_PASS\n" : "VECTOR_SMOKE_FAIL\n");
        return passed ? 0 : 1;
    }
    window.show();
    return app.exec();
}
