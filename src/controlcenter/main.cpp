// SPDX-License-Identifier: GPL-3.0-or-later
#include <QtWidgets>
#include <functional>
class ProgressDialog:public QDialog {
public:
 using QDialog::QDialog;
 bool running=true;
 void reject() override {if(!running)QDialog::reject();}
protected:
 void closeEvent(QCloseEvent *event) override {if(running)event->ignore();else QDialog::closeEvent(event);}
};
class Center:public QMainWindow {
 QListWidget *nav; QStackedWidget *pages; bool first;
 QString config() {return QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/aether";}
 void launch(QString command,QStringList args={}) {if(!QProcess::startDetached(command,args))QMessageBox::warning(this,"Could not open",command+" is unavailable.");}
 void task(QString command,QStringList args={}) {
  auto d=new ProgressDialog(this);d->setWindowModality(Qt::ApplicationModal);d->setAttribute(Qt::WA_DeleteOnClose);d->setWindowTitle("Aether — progress");d->resize(680,440);auto v=new QVBoxLayout(d);auto text=new QPlainTextEdit;text->setReadOnly(true);text->setAccessibleName("Operation output");v->addWidget(text);auto close=new QPushButton("Close");close->setEnabled(false);v->addWidget(close);connect(close,&QPushButton::clicked,d,&QDialog::accept);
  auto p=new QProcess(d);p->setProcessChannelMode(QProcess::MergedChannels);
  connect(p,&QProcess::readyReadStandardOutput,d,[p,text]{text->appendPlainText(QString::fromUtf8(p->readAllStandardOutput()));});
  connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),d,[d,text,close](int code,QProcess::ExitStatus state){d->running=false;text->appendPlainText(code==0&&state==QProcess::NormalExit?"Completed.":"The operation did not complete. Review the message above.");close->setEnabled(true);});
  connect(p,&QProcess::errorOccurred,d,[d,text,close,p]{text->appendPlainText(p->errorString());if(p->state()==QProcess::NotRunning){d->running=false;close->setEnabled(true);}});
  d->show();p->start(command,args);
 }
 QVBoxLayout *page(QString title,QString subtitle,QString icon) {
  auto item=new QListWidgetItem(QIcon::fromTheme(icon),title,nav);item->setToolTip(subtitle);item->setSizeHint(QSize(220,44));
  auto sc=new QScrollArea;sc->setWidgetResizable(true);auto w=new QWidget;auto v=new QVBoxLayout(w);v->setContentsMargins(28,24,28,24);v->setSpacing(14);auto h=new QLabel(title);h->setStyleSheet("font-size:26px;font-weight:600");v->addWidget(h);auto sub=new QLabel(subtitle);sub->setWordWrap(true);v->addWidget(sub);v->addStretch();sc->setWidget(w);pages->addWidget(sc);return v;
 }
 void note(QVBoxLayout*v,QString text){auto l=new QLabel(text);l->setWordWrap(true);l->setTextFormat(Qt::PlainText);v->insertWidget(v->count()-1,l);}
 void button(QVBoxLayout*v,QString title,QString tip,QString icon,std::function<void()> fn){auto b=new QPushButton(QIcon::fromTheme(icon),title);b->setToolTip(tip);b->setAccessibleName(title);b->setMinimumHeight(40);v->insertWidget(v->count()-1,b);connect(b,&QPushButton::clicked,this,fn);}
 void settings(QVBoxLayout*v,QString name,QString module,QString icon){button(v,name,"Open "+name,icon,[=]{launch("systemsettings",{module});});}
 void chooseCheckpoint() {
  QFile file("/var/lib/aether-recovery-status.json");if(!file.open(QIODevice::ReadOnly)){QMessageBox::information(this,"No checkpoints","Create a system checkpoint first.");return;}
  const auto records=QJsonDocument::fromJson(file.readAll()).object().value("checkpoints").toArray();
  QDialog dialog(this);dialog.setWindowTitle("Try a recovery checkpoint");auto layout=new QVBoxLayout(&dialog);auto choices=new QComboBox;choices->setAccessibleName("Recovery checkpoint");layout->addWidget(choices);
  QRegularExpression valid("^[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$");
  for(const auto &value:records){auto record=value.toObject();auto id=record.value("id").toString();auto state=record.value("state").toString();if(valid.match(id).hasMatch()&&(state=="ready"||state=="pending"||state=="healthy"))choices->addItem(record.value("created").toString()+" ("+state+")",id);}
  if(!choices->count()){QMessageBox::information(this,"No ready checkpoints","No complete checkpoint is available.");return;}
  auto note=new QLabel("Select one trial boot. Your home files remain shared. No restart occurs automatically.");note->setWordWrap(true);layout->addWidget(note);
  auto buttons=new QDialogButtonBox(QDialogButtonBox::Ok|QDialogButtonBox::Cancel);layout->addWidget(buttons);connect(buttons,&QDialogButtonBox::accepted,&dialog,&QDialog::accept);connect(buttons,&QDialogButtonBox::rejected,&dialog,&QDialog::reject);
  if(dialog.exec()==QDialog::Accepted)task("pkexec",{"/usr/libexec/aether-system-admin","recovery-boot",choices->currentData().toString()});
 }
 void exportDiagnostics() {
  auto path=QFileDialog::getSaveFileName(this,"Save basic diagnostic summary",QDir::homePath()+"/aether-diagnostics-"+QDateTime::currentDateTimeUtc().toString("yyyyMMdd-HHmmss")+".json","JSON (*.json)");
  if(path.isEmpty())return;
  if(QFileInfo::exists(path)){QMessageBox::warning(this,"Choose a new file","Diagnostics never overwrite an existing file. Choose a new filename.");return;}
  if(QMessageBox::question(this,"Export diagnostic summary?","Include system version, disk capacity and selected service states? Logs, users, network addresses, credentials and personal files are excluded. Review the file before sharing.")==QMessageBox::Yes)task("aether-diagnostics",{"--output",path});
 }
 void networkProfile(bool trusted) {
  QProcess query;query.start("nmcli",{"--terse","--escape","no","--fields","UUID,NAME","connection","show","--active"});
  if(!query.waitForFinished(5000)||query.exitCode()!=0){query.kill();QMessageBox::warning(this,"Network unavailable","Could not read active connections. No trust setting was changed.");return;}
  QDialog dialog(this);dialog.setWindowTitle(trusted?"Choose a home network":"Choose a public network");auto layout=new QVBoxLayout(&dialog);
  auto explanation=new QLabel(trusted?"Choose a connection you trust. Home-scoped firewall exceptions apply only while this saved connection is active.":"Remove home trust from this connection. Global exceptions you opened separately are preserved.");explanation->setWordWrap(true);layout->addWidget(explanation);
  auto choices=new QComboBox;choices->setAccessibleName("Active network connection");layout->addWidget(choices);
  QRegularExpression identity("^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$");
  for(const auto &line:QString::fromUtf8(query.readAllStandardOutput()).split('\n')){auto uuid=line.left(36);if(line.size()>37&&line[36]==':'&&identity.match(uuid).hasMatch())choices->addItem(line.mid(37),uuid);}
  if(!choices->count()){QMessageBox::information(this,"No active connections","Connect to a network first. No trust setting was changed.");return;}
  auto buttons=new QDialogButtonBox(QDialogButtonBox::Ok|QDialogButtonBox::Cancel);layout->addWidget(buttons);connect(buttons,&QDialogButtonBox::accepted,&dialog,&QDialog::accept);connect(buttons,&QDialogButtonBox::rejected,&dialog,&QDialog::reject);
  if(dialog.exec()==QDialog::Accepted)task("pkexec",{"/usr/libexec/aether-system-admin",trusted?"network-home":"network-public",choices->currentData().toString()});
 }
 void admin(QString action){task("pkexec",{"/usr/libexec/aether-system-admin",action});}
public:
 bool capture(const QString &directory){if(!QDir().mkpath(directory))return false;for(int i=0;i<nav->count();++i){nav->setCurrentRow(i);QApplication::processEvents();if(!grab().save(directory+QString("/settings-%1.png").arg(i,2,10,QChar('0'))))return false;}return true;}
 Center(bool welcome):first(welcome){setWindowTitle(welcome?"Welcome to Aether":"Aether Settings");resize(1020,720);setMinimumSize(760,520);auto root=new QWidget;auto row=new QHBoxLayout(root);nav=new QListWidget;nav->setAccessibleName("Settings categories");nav->setFixedWidth(230);nav->setIconSize(QSize(24,24));pages=new QStackedWidget;row->addWidget(nav);row->addWidget(pages,1);setCentralWidget(root);connect(nav,&QListWidget::currentRowChanged,pages,&QStackedWidget::setCurrentIndex);
  auto v=page("Welcome","Make Aether comfortable for you. You can revisit every setting later.","start-here");
  settings(v,"Keyboard and layout","kcm_keyboard","input-keyboard");settings(v,"Time zone","kcm_clock","preferences-system-time");settings(v,"Display and scaling","kcm_kscreen","video-display");settings(v,"Users and passwords","kcm_users","system-users");
  auto test=new QLineEdit;test->setPlaceholderText("Test your keyboard here — letters, numbers and arrow keys");test->setAccessibleName("Keyboard test");v->insertWidget(v->count()-1,test);
  button(v,"Test sound","Play Aether's sound preview without changing volume","audio-volume-high",[=]{task("aether-sounds",{"--preview","desktop-login"});});
  note(v,"Review Backups and Privacy before finishing. AI runs on this device and starts when Nimbrel is opened. No account or cloud service is required.");
  button(v,"Finish setup","Save first-run completion for this account","dialog-ok-apply",[=]{QDir().mkpath(config());QSaveFile f(config()+"/welcome-v1.json");if(f.open(QIODevice::WriteOnly)){f.write("{\"completed\":true}\n");if(f.commit()){QMessageBox::information(this,"Ready","Setup saved. Open Aether Settings whenever you need it.");if(first)close();}}});
  v=page("Updates","Check automatically. Install only when you approve. Never restart automatically.","system-software-update");
  button(v,"Check Aether updates","Verify signed repository metadata and show available updates","view-refresh",[=]{task("aether-update",{"check"});});
  button(v,"Update status","Show repository configuration, last check and pending changes","dialog-information",[=]{task("aether-update",{"status"});});
  button(v,"Install staged update","Review and approve a verified system update","system-software-install",[=]{launch("konsole",{"-e","sudo","aether-update","install"});});
  note(v,"A repository is usable only after an administrator provisions trusted release keys. An unconfigured or expired repository is reported as an error, never as 'up to date'.");
  v=page("Applications","Discover applications, inspect permissions, and manage installed software.","system-software-install");
  button(v,"Open app store","Browse applications with KDE Discover","plasmadiscover",[=]{launch("plasma-discover");});
  button(v,"Enable Flathub for my account","Add the signed Flathub remote; no app is installed automatically","list-add",[=]{if(QMessageBox::question(this,"Enable Flathub?","This adds Flathub as a third-party application source and downloads its catalog. Applications may contain third-party binaries. Enable it for your account?")==QMessageBox::Yes)task("flatpak",{"--user","remote-add","--if-not-exists","flathub","https://dl.flathub.org/repo/flathub.flatpakrepo"});});
  settings(v,"Application permissions","kcm_app-permissions","security-high");
  v=page("Recovery","Recover the system separately from restoring personal files.","document-revert");
  button(v,"Recovery status","Show available system checkpoints","dialog-information",[=]{task("aether-recovery",{"status"});});
  button(v,"Create system checkpoint","Save a recoverable system copy; requires free disk space","document-save",[=]{if(QMessageBox::question(this,"Create checkpoint?","Save a complete system copy on this disk? It needs free space and does not replace an independent backup. User homes remain shared.")==QMessageBox::Yes)admin("recovery-create");});
  button(v,"Try a recovery checkpoint","Choose a checkpoint for one trial boot; no automatic restart","document-revert",[=]{chooseCheckpoint();});
  button(v,"Export basic diagnostics","Save a reviewable summary without logs or personal files","document-save",[=]{exportDiagnostics();});
  button(v,"Open recovery tools","Review checkpoints and offline recovery instructions","tools-wizard",[=]{launch("konsole",{"-e","aether-recovery","help"});});
  note(v,"Use the Aether live ISO for offline repair. Checkpoints on this disk do not protect against disk failure. Keep independent backups.");
  v=page("Backups","Encrypted backups to a destination you choose. Keep the recovery passphrase safe.","document-save");
  button(v,"Set up encrypted backups","Choose a mounted independent drive or shared folder","folder-new",[=]{launch("konsole",{"-e","sudo","aether-backup","setup"});});
  button(v,"Back up now","Run the configured encrypted backup","document-save",[=]{launch("konsole",{"-e","sudo","aether-backup","run"});});
  button(v,"Check backups","Verify the backup repository","dialog-ok",[=]{launch("konsole",{"-e","sudo","aether-backup","check"});});
  v=page("Performance","Keep older computers responsive. Nimbrel loads only when opened and unloads after inactivity.","speedometer");
  button(v,"Use lightweight mode","Reduce animation and blur, and disable background file indexing","battery-profile-powersave",[=]{task("aether-preferences",{"lightweight"});});
  button(v,"Restore previous preferences","Restore the settings saved before lightweight mode","edit-undo",[=]{task("aether-preferences",{"restore"});});
  settings(v,"Power and sleep","kcm_powerdevilprofilesconfig","preferences-system-power-management");
  v=page("Privacy and AI","Nimbrel uses local processing. No file indexing is enabled by default.","security-high");
  note(v,"Nimbrel cannot run commands or install software. Folder search is opt-in and local. You review excerpts before attaching them to a chat. Text indexes contain readable copies; use disk encryption to protect them at rest.");
  button(v,"Choose a searchable folder","Allow local indexing of a specific non-hidden folder in your home","folder-add",[=]{auto d=QFileDialog::getExistingDirectory(this,"Choose a folder to index",QDir::homePath());if(!d.isEmpty())task("nimbrel-library",{"add",d});});
  button(v,"Build local text index","Index approved TXT, Markdown, RST and CSV files; up to 64 MiB","system-search",[=]{task("nimbrel-library",{"rebuild"});});
  button(v,"Remove folder access and index","Delete local search data and revoke all indexed folders","edit-delete",[=]{if(QMessageBox::question(this,"Remove index?","Delete the local text index and revoke folder access? Original documents are preserved.")==QMessageBox::Yes)task("nimbrel-library",{"clear"});});
  button(v,"Open Nimbrel","Manage conversations and temporary chats","org.aether.Nimbrel",[=]{launch("nimbrel");});
  button(v,"Disable AI on this device","Stop local AI and prevent activation until enabled again","media-playback-stop",[=]{if(QMessageBox::question(this,"Disable local AI?","Stop Nimbrel services for all users on this device?")==QMessageBox::Yes)admin("ai-disable");});
  button(v,"Enable on-demand AI","Allow Nimbrel to start when opened","media-playback-start",[=]{admin("ai-enable");});
  v=page("Accessibility","Use Aether with a keyboard, screen reader, magnification, and reduced motion.","preferences-desktop-accessibility");
  settings(v,"Accessibility settings","kcm_access","preferences-desktop-accessibility");settings(v,"Text and fonts","kcm_fonts","preferences-desktop-font");settings(v,"Colors and contrast","kcm_colors","preferences-desktop-color");
  button(v,"Start screen reader","Start Orca for this desktop session","audio-volume-high",[=]{launch("orca");});
  note(v,"All Aether Settings controls support keyboard focus and accessible names. Physical assistive-device testing remains important.");
  v=page("Network privacy","Public by default. Explicitly trust a saved connection before enabling home-scoped sharing.","network-wireless");
  button(v,"Mark a connection as Home","Choose a trusted active network for home-scoped firewall exceptions","network-connect",[=]{networkProfile(true);});
  button(v,"Mark a connection as Public","Remove home trust from an active connection","security-high",[=]{networkProfile(false);});
  settings(v,"Network connections","kcm_networkmanagement","network-wireless");
  note(v,"A private IP address alone does not establish trust. Phone sharing requires a Home connection and separate approval. Previously opened global ports are unchanged.");
  v=page("USB protection","Optional device authorization. Enroll your keyboard and mouse before blocking unknown USB devices.","drive-removable-media-usb");
  button(v,"Try USB protection","Start an administrator-authorized trial with automatic rollback unless you confirm","security-high",[=]{launch("konsole",{"--hold","-e","sudo","aether-usbguard","setup"});});
  button(v,"USB protection status","Review the USBGuard service status","dialog-information",[=]{launch("konsole",{"--hold","-e","sudo","aether-usbguard","status"});});
  button(v,"Disable on next boot","Disable USB protection after your next manual restart","security-low",[=]{launch("konsole",{"--hold","-e","sudo","aether-usbguard","disable"});});
  note(v,"Protection stays off until you choose it. Setup captures connected devices and asks you to confirm that input still works. Keep recovery media available. A connected device's identity is not proof that its firmware is trustworthy.");
  v=page("Phone connection","Pair devices you trust. Features become available after you approve pairing.","smartphone");
  button(v,"Open KDE Connect","Pair your phone and choose sharing plugins","kdeconnect",[=]{launch("kdeconnect-app");});
  button(v,"Allow phone connections on Home networks","Open KDE Connect ports only on trusted connections, from private and link-local addresses","network-connect",[=]{if(QMessageBox::question(this,"Allow phone connections?","Allow KDE Connect on connections marked Home in Network privacy? Public connections remain closed. Approve only devices you trust.")==QMessageBox::Yes)admin("phone-enable");});
  button(v,"Disable phone network access","Remove Aether's phone firewall exception","network-disconnect",[=]{admin("phone-disable");});
  note(v,"Install KDE Connect on your phone. Devices must be able to reach each other; VM NAT may prevent discovery. Approve pairing on both devices. Firewall access is not opened silently.");
  v=page("Hardware","Inspect devices, manage connectivity, and review available firmware updates.","computer");
  settings(v,"Wi-Fi and networking","kcm_networkmanagement","network-wireless");settings(v,"Bluetooth","kcm_bluetooth","preferences-system-bluetooth");settings(v,"Displays","kcm_kscreen","video-display");settings(v,"Audio devices","kcm_pulseaudio","audio-card");
  button(v,"Firmware devices","List devices supported by fwupd","computer",[=]{task("fwupdmgr",{"get-devices"});});
  button(v,"Check firmware updates","Contact LVFS to refresh signed metadata and list updates","view-refresh",[=]{admin("firmware-check");});
  button(v,"Install firmware updates","Review updates and confirm in the firmware manager","system-software-update",[=]{launch("konsole",{"-e","fwupdmgr","update"});});
  note(v,"Firmware support depends on the device and vendor. Virtual machines commonly have no supported firmware devices. No firmware is flashed automatically.");
  nav->setCurrentRow(0);
 }
};
int main(int argc,char**argv){QApplication app(argc,argv);app.setApplicationName("Aether Settings");app.setOrganizationName("Aether");const bool first=app.arguments().contains("--first-run");auto path=QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/aether/welcome-v1.json";if(first&&QFileInfo::exists(path))return 0;Center c(first);c.show();const auto args=app.arguments();int capture=args.indexOf("--capture-dir");if(capture>=0){if(capture+1>=args.size())return 2;QTimer::singleShot(1000,&app,[&]{app.exit(c.capture(args[capture+1])?0:1);});}return app.exec();}
