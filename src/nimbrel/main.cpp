#include <QtWidgets>
#include <functional>

class SafeText : public QTextBrowser {
protected:
 QVariant loadResource(int,const QUrl&) override { return {}; }
public:
 SafeText(QWidget *p=nullptr):QTextBrowser(p){setOpenLinks(false);setOpenExternalLinks(false);setFrameShape(QFrame::NoFrame);}
};
class Composer : public QPlainTextEdit {
public:
 std::function<void()> submit;
 void keyPressEvent(QKeyEvent *e) override {
  if((e->key()==Qt::Key_Return||e->key()==Qt::Key_Enter)&&!(e->modifiers()&Qt::ShiftModifier)){if(submit)submit();e->accept();return;}
  QPlainTextEdit::keyPressEvent(e);
 }
};
class Nimbrel : public QMainWindow {
 QLineEdit *search; QListWidget *chats; QLabel *state,*model,*title,*privacy;
 QScrollArea *scroll; QWidget *messages; QVBoxLayout *cards; Composer *input;
 QPlainTextEdit *attachment; QWidget *attachmentBox; QComboBox *mode;
 QToolButton *send,*stop,*temporary; QProgressBar *progress;
 QPointer<QProcess> active; QJsonArray conversations; QString current; bool ephemeral=false,dark=true,ready=false;
 QByteArray output; QString latest; QTimer statusTimer;
 QString storePath() const {return QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/conversations.json";}
 QIcon symbol(const QString &name) const {
  QPixmap pix(48,48);pix.fill(Qt::transparent);QPainter p(&pix);p.setRenderHint(QPainter::Antialiasing);p.scale(2,2);
  p.setPen(QPen(QColor(dark?"#ececec":"#202020"),1.7,Qt::SolidLine,Qt::RoundCap,Qt::RoundJoin));
  auto line=[&](qreal a,qreal b,qreal c,qreal d){p.drawLine(QPointF(a,b),QPointF(c,d));};
  auto path=[&](std::initializer_list<QPointF> points){QPainterPath v;bool first=true;for(auto q:points){if(first){v.moveTo(q);first=false;}else v.lineTo(q);}p.drawPath(v);};
  if(name=="document-new"){p.drawRoundedRect(QRectF(3,3,15,18),2,2);line(9,10,15,10);line(12,7,12,13);}
  else if(name=="document-edit"){path({{4,16},{15,5},{19,9},{8,20},{3,21},{4,16}});line(13,7,17,11);}
  else if(name=="edit-delete"){path({{6,7},{7,21},{17,21},{18,7}});line(4,7,20,7);path({{9,7},{9,3},{15,3},{15,7}});line(10,11,10,17);line(14,11,14,17);}
  else if(name=="preferences-system"){for(int y:{6,12,18})line(3,y,21,y);p.setBrush(QColor(dark?"#212121":"#ffffff"));p.drawEllipse(QPointF(8,6),2,2);p.drawEllipse(QPointF(16,12),2,2);p.drawEllipse(QPointF(10,18),2,2);}
  else if(name=="view-private"){p.drawRoundedRect(QRectF(5,10,14,11),2,2);p.drawArc(QRectF(8,3,8,13),0,180*16);line(12,15,12,17);}
  else if(name=="document-save"){line(12,3,12,15);path({{7,10},{12,15},{17,10}});path({{4,15},{4,21},{20,21},{20,15}});}
  else if(name=="weather-clear-night"){QPainterPath v;v.moveTo(17,3);v.cubicTo(3,-1,0,20,14,21);v.cubicTo(19,21,22,17,22,14);v.cubicTo(10,18,8,7,17,3);p.drawPath(v);}
  else if(name=="window-close"){line(5,5,19,19);line(19,5,5,19);}
  else if(name=="mail-attachment"){QPainterPath v;v.moveTo(9,17);v.lineTo(17,9);v.cubicTo(21,5,16,1,13,4);v.lineTo(4,13);v.cubicTo(-2,20,7,26,13,20);v.lineTo(21,12);p.drawPath(v);line(8,14,15,7);}
  else if(name=="utilities-system-monitor"){p.drawRoundedRect(QRectF(3,3,18,14),2,2);line(12,17,12,21);line(7,21,17,21);path({{5,11},{8,11},{10,7},{13,14},{16,9},{19,9}});}
  else if(name=="media-playback-stop"){p.drawRoundedRect(QRectF(6,6,12,12),2,2);}
  else if(name=="mail-send"){line(12,20,12,4);path({{5,11},{12,4},{19,11}});}
  else if(name=="edit-copy"){p.drawRoundedRect(QRectF(8,8,12,13),2,2);path({{15,5},{15,3},{3,3},{3,16},{5,16}});}
  else if(name=="audio-volume-high"){path({{3,9},{7,9},{12,4},{12,20},{7,15},{3,15},{3,9}});p.drawArc(QRectF(10,6,10,12),-65*16,130*16);p.drawArc(QRectF(10,3,15,18),-60*16,120*16);}
  else if(name=="view-refresh"){p.drawArc(QRectF(4,4,16,16),40*16,290*16);path({{15,3},{20,7},{21,2}});}
  else if(name=="code-context"){path({{7,6},{2,12},{7,18}});path({{17,6},{22,12},{17,18}});line(14,3,10,21);}
  else {p.drawRoundedRect(QRectF(3,4,18,14),3,3);path({{6,18},{6,22},{11,18}});}
  p.end();return QIcon(pix);
 }
 QToolButton *icon(const QString &name,const QString &tip,std::function<void()> fn) {
  auto b=new QToolButton;auto i=symbol(name);b->setProperty("symbolName",name);
  b->setIcon(i);b->setIconSize(QSize(20,20));b->setFixedSize(36,36);b->setToolTip(tip);b->setAccessibleName(tip);b->setCursor(Qt::PointingHandCursor);
  connect(b,&QToolButton::clicked,this,[fn]{fn();});return b;
 }
 int index() const {for(int i=0;i<conversations.size();++i)if(conversations[i].toObject()["id"].toString()==current)return i;return -1;}
 QJsonObject chat() const {auto n=index();return n>=0?conversations[n].toObject():QJsonObject();}
 void save() {
  if(ephemeral)return;
  const QString path=storePath();QDir().mkpath(QFileInfo(path).absolutePath());QFile::setPermissions(QFileInfo(path).absolutePath(),QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);
  QJsonArray retained;for(const auto &v:conversations)if(!v.toObject()["temporary"].toBool())retained.append(v);
  QSaveFile f(path);if(!f.open(QIODevice::WriteOnly)){state->setText("Could not save chat history");return;}
  f.setPermissions(QFile::ReadOwner|QFile::WriteOwner);f.write(QJsonDocument(retained).toJson(QJsonDocument::Compact));if(!f.commit())state->setText("Could not save chat history");
 }
 void update(const QJsonObject &v) {int n=index();if(n>=0)conversations[n]=v;save();list();}
 void list() {
  const QSignalBlocker block(chats);chats->clear();const auto filter=search->text();
  for(int i=conversations.size()-1;i>=0;--i){auto c=conversations[i].toObject();if(c["temporary"].toBool()&&c["id"].toString()!=current)continue;
   QString name=c["title"].toString("New chat");if(!name.contains(filter,Qt::CaseInsensitive))continue;
   auto item=new QListWidgetItem(symbol("mail-message"),name,chats);item->setData(Qt::UserRole,c["id"].toString());item->setToolTip(name);if(c["id"].toString()==current)chats->setCurrentItem(item);
  }
 }
 void newChat(bool temp=false) {
  if(active)return;
  // Temporary conversations are discarded when leaving them.
  for(int i=conversations.size()-1;i>=0;--i)if(conversations[i].toObject()["temporary"].toBool())conversations.removeAt(i);
  ephemeral=temp;current=QUuid::createUuid().toString(QUuid::WithoutBraces);
  conversations.append(QJsonObject{{"id",current},{"title",temp?"Temporary chat":"New chat"},{"messages",QJsonArray()},{"temporary",temp}});
  temporary->setChecked(temp);input->clear();attachment->clear();attachmentBox->hide();render();list();
 }
 void render() {
  while(auto child=cards->takeAt(0)){if(child->widget())child->widget()->deleteLater();delete child;}
  auto c=chat();title->setText(c["title"].toString());privacy->setText(ephemeral?"Temporary chat · Not saved":"Chats are saved only on this device");
  const auto history=c["messages"].toArray();latest.clear();
  if(history.isEmpty()) {
   auto welcome=new QLabel("What would you like to explore?");welcome->setAlignment(Qt::AlignCenter);welcome->setObjectName("welcome");cards->addSpacing(80);cards->addWidget(welcome);
   auto note=new QLabel("Your assistant, running inside Aether. No account or pairing required.");note->setWordWrap(true);note->setAlignment(Qt::AlignCenter);cards->addWidget(note);
   auto suggestions=new QWidget;auto grid=new QGridLayout(suggestions);
   const QStringList examples={"Explain a Linux concept","Help me write an email","Review a piece of code","Plan my next project"};
   for(int i=0;i<examples.size();++i){auto b=new QPushButton(examples[i]);b->setMinimumHeight(48);connect(b,&QPushButton::clicked,this,[this,examples,i]{input->setPlainText(examples[i]);input->setFocus();});grid->addWidget(b,i/2,i%2);}cards->addWidget(suggestions);
  }
  for(int n=0;n<history.size();++n) {
   const auto m=history[n].toObject();const bool user=m["role"].toString()=="user";const QString text=m["content"].toString();
   auto frame=new QFrame;frame->setObjectName(user?"userCard":"assistantCard");auto v=new QVBoxLayout(frame);v->setContentsMargins(18,14,18,12);
   auto name=new QLabel(user?"You":"Nimbrel");name->setObjectName("role");v->addWidget(name);
   auto browser=new SafeText;browser->setMarkdown(text);browser->setMinimumHeight(70);browser->setMaximumHeight(1100);browser->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Preferred);
   connect(browser,&QTextBrowser::anchorClicked,this,[this](const QUrl &url){if((url.scheme()=="https"||url.scheme()=="http")&&QMessageBox::question(this,"Open link?","Open this link in your browser?\n"+url.toString())==QMessageBox::Yes)QDesktopServices::openUrl(url);});
   v->addWidget(browser);QTimer::singleShot(0,browser,[browser]{browser->document()->setTextWidth(browser->viewport()->width());browser->setFixedHeight(qBound(70,int(browser->document()->size().height())+16,1100));});
   auto actions=new QHBoxLayout;actions->addWidget(icon("edit-copy","Copy message",[text]{QApplication::clipboard()->setText(text);}));
   if(user)actions->addWidget(icon("document-edit","Edit and resend from here",[this,n,text]{if(active)return;auto c=chat();auto h=c["messages"].toArray();while(h.size()>n)h.removeLast();c["messages"]=h;update(c);input->setPlainText(text);render();input->setFocus();}));
   else {
    latest=text;
    actions->addWidget(icon("audio-volume-high","Read aloud",[this,text]{auto p=new QProcess(this);connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),p,&QObject::deleteLater);p->start("/usr/bin/spd-say",{"--",text.left(8000)});}));
    if(n==history.size()-1)actions->addWidget(icon("view-refresh","Regenerate response",[this]{regenerate();}));
    if(text.contains("```"))actions->addWidget(icon("code-context","Copy code blocks",[text]{QStringList code;QRegularExpression re("```[^\\n]*\\n([\\s\\S]*?)```");auto matches=re.globalMatch(text);while(matches.hasNext())code<<matches.next().captured(1);QApplication::clipboard()->setText(code.join("\n\n"));}));
   }
   actions->addStretch();v->addLayout(actions);cards->addWidget(frame);
  }
  cards->addStretch();QTimer::singleShot(50,this,[this]{scroll->verticalScrollBar()->setValue(scroll->verticalScrollBar()->maximum());});
 }
 void busy(bool b) {send->setEnabled(!b&&ready);stop->setEnabled(b);input->setReadOnly(b);chats->setEnabled(!b);mode->setEnabled(!b);temporary->setEnabled(!b);progress->setVisible(b);}
 void call(QJsonObject req,std::function<void(QJsonObject)> cb) {
  if(active)return;
  auto p=new QProcess(this);active=p;output.clear();busy(true);
  connect(p,&QProcess::readyReadStandardOutput,this,[this,p]{output+=p->readAllStandardOutput();});
  auto finish=[this,p,cb]{if(p->property("done").toBool())return;p->setProperty("done",true);output+=p->readAllStandardOutput();auto result=QJsonDocument::fromJson(output).object();if(result.isEmpty())result={{"ok",false},{"error",p->property("cancelled").toBool()?"Stopped. The local engine may finish its current request.":"The local helper stopped unexpectedly."}};active=nullptr;busy(false);p->deleteLater();cb(result);};
  connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish](int,QProcess::ExitStatus){finish();});
  connect(p,&QProcess::errorOccurred,this,[finish](QProcess::ProcessError e){if(e==QProcess::FailedToStart)finish();});
  connect(p,&QProcess::started,this,[p,req]{p->write(QJsonDocument(req).toJson(QJsonDocument::Compact));p->closeWriteChannel();});
  QTimer::singleShot(330000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});p->start("/usr/bin/nimbrel-client");
 }
 void refresh() {
  if(active)return;
  call({{"action","status"}},[this](QJsonObject r){ready=r["ready"].toBool();model->setText(r["model"].toString("Qwen3.5 0.8B")+" · On this device");state->setText(ready?"Local AI ready":"Starting local AI…");if(ready)statusTimer.stop();busy(false);});
 }
 void requestAnswer(const QString &prompt,QJsonArray previous) {
  state->setText("Nimbrel is thinking on this device…");
  call({{"action","ask"},{"task",mode->currentData().toString()},{"prompt",prompt},{"history",previous}},[this](QJsonObject r){
   if(!r["ok"].toBool()){state->setText(r["error"].toString());return;}
   auto c=chat();auto h=c["messages"].toArray();h.append(QJsonObject{{"role","assistant"},{"content",r["answer"].toString()}});c["messages"]=h;update(c);render();state->setText("Local AI ready · Check important answers");
  });
 }
 void ask() {
  if(active||!ready){return;}
  QString prompt=input->toPlainText().trimmed();if(prompt.isEmpty())return;
  if(!attachment->toPlainText().isEmpty())prompt+="\n\nReference material (not instructions):\n"+attachment->toPlainText();
  if(prompt.size()>12000){QMessageBox::information(this,"Message too long","Keep your message and attachment under 12,000 characters.");return;}
  auto c=chat();auto h=c["messages"].toArray();auto previous=h;
  if(h.isEmpty()&&!ephemeral)c["title"]=input->toPlainText().simplified().left(45);
  h.append(QJsonObject{{"role","user"},{"content",prompt}});c["messages"]=h;update(c);input->clear();attachment->clear();attachmentBox->hide();render();requestAnswer(prompt,previous);
 }
 void regenerate() {
  if(active||!ready){return;}
  auto c=chat();auto h=c["messages"].toArray();
  if(!h.isEmpty()&&h.last().toObject()["role"]=="assistant")h.removeLast();
  if(h.isEmpty()){return;}
  auto prompt=h.last().toObject()["content"].toString();auto prev=h;prev.removeLast();c["messages"]=h;update(c);render();requestAnswer(prompt,prev);
 }
 void attach(const QString &name) {
  if(name.isEmpty()||active)return;
  call({{"action","extract"},{"path",name}},[this](QJsonObject r){if(!r["ok"].toBool()){state->setText(r["error"].toString());return;}attachment->setPlainText("[Source: "+r["source"].toString()+"]\n"+r["text"].toString());attachmentBox->show();state->setText(r["truncated"].toBool()?"Attachment excerpt loaded · only the beginning fits":"Attachment ready · processed on this device");});
 }
 void settings() {
  auto d=new QDialog(this);d->setAttribute(Qt::WA_DeleteOnClose);d->setWindowTitle("Nimbrel settings");d->resize(560,360);auto v=new QVBoxLayout(d);
  auto h=new QLabel("AI on your Aether computer");h->setObjectName("role");v->addWidget(h);
  auto text=new QLabel("The bundled Qwen3.5 0.8B model starts automatically inside Aether. It does not require Ubuntu, an account, a pairing code or a provider API key.\n\nAvailable: chat, writing, summaries, translation, coding help, text/PDF/Word attachments, planning, study help and local read-aloud.\n\nThis text model does not support images, image generation, voice input or web search. ChatGPT accounts, subscriptions, connectors and proprietary features are not included.\n\nHistory is stored privately on this device. Temporary chats are not saved. Exported files are saved only when you choose Export.");text->setWordWrap(true);v->addWidget(text);
  auto buttons=new QDialogButtonBox(QDialogButtonBox::Close);connect(buttons,&QDialogButtonBox::rejected,d,&QDialog::close);v->addWidget(buttons);d->show();
 }
 void theme() {
  const QString bg=dark?"#212121":"#ffffff",side=dark?"#171717":"#f5f5f5",fg=dark?"#ececec":"#202020",muted=dark?"#a5a5a5":"#666666",border=dark?"#414141":"#dddddd",card=dark?"#303030":"#f1f1f1";
  for(auto b:findChildren<QToolButton*>())if(b->property("symbolName").isValid())b->setIcon(symbol(b->property("symbolName").toString()));
  if(chats)list();
  QPalette pal=qApp->palette();pal.setColor(QPalette::Window,QColor(bg));pal.setColor(QPalette::WindowText,QColor(fg));pal.setColor(QPalette::Text,QColor(fg));pal.setColor(QPalette::Base,QColor(bg));pal.setColor(QPalette::ButtonText,QColor(fg));pal.setColor(QPalette::HighlightedText,QColor(fg));pal.setColor(QPalette::Highlight,QColor(card));qApp->setPalette(pal);
  setStyleSheet(QString("QToolTip{background:%2;color:%3;border:1px solid %5;padding:6px;} QMainWindow,QDialog{background:%1;color:%3;} QWidget{color:%3;} #sidebar{background:%2;} QScrollArea,QScrollArea>QWidget>QWidget,QTextBrowser{background:transparent;border:0;} #userCard{background:%6;border-radius:16px;} #assistantCard{background:transparent;} #role{font-weight:600;} #welcome{font-size:26px;font-weight:600;} QLineEdit,QPlainTextEdit,QComboBox{background:%6;border:1px solid %5;border-radius:10px;padding:10px;color:%3;} QListWidget{background:transparent;border:0;} QListWidget::item{padding:10px;border-radius:8px;} QListWidget::item:selected{background:%6;color:%3;} QToolButton:hover,QPushButton:hover{background:%6;} QToolButton{border:0;border-radius:8px;background:transparent;} QToolButton:disabled{color:%4;} QPushButton{background:%2;border:1px solid %5;border-radius:10px;padding:10px;} QLabel#muted{color:%4;font-size:11px;} QProgressBar{border:0;background:%2;max-height:3px;} QProgressBar::chunk{background:#a5a5a5;}").arg(bg,side,fg,muted,border,card));
 }
public:
 Nimbrel() {
  setWindowTitle("Nimbrel · Aether AI");setWindowIcon(QIcon::fromTheme("org.aether.Nimbrel"));resize(1180,800);
  auto central=new QWidget;auto root=new QHBoxLayout(central);root->setContentsMargins(0,0,0,0);root->setSpacing(0);
  auto sidebar=new QWidget;sidebar->setObjectName("sidebar");sidebar->setFixedWidth(240);auto sv=new QVBoxLayout(sidebar);sv->setContentsMargins(16,18,16,18);
  auto heading=new QHBoxLayout;auto brand=new QLabel("Nimbrel");auto font=brand->font();font.setPointSize(19);font.setBold(true);brand->setFont(font);heading->addWidget(brand);heading->addStretch();heading->addWidget(icon("document-new","New chat",[this]{newChat();}));sv->addLayout(heading);
  search=new QLineEdit;search->setPlaceholderText("Search chats");search->setAccessibleName("Search conversation history");sv->addWidget(search);chats=new QListWidget;chats->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);chats->setTextElideMode(Qt::ElideRight);sv->addWidget(chats,1);
  auto bottom=new QHBoxLayout;bottom->addWidget(icon("document-edit","Rename chat",[this]{if(active)return;bool ok=false;auto name=QInputDialog::getText(this,"Rename chat","Title",QLineEdit::Normal,chat()["title"].toString(),&ok);if(ok&&!name.trimmed().isEmpty()){auto c=chat();c["title"]=name.left(100);update(c);render();}}));
  bottom->addWidget(icon("edit-delete","Delete chat",[this]{if(active)return;if(QMessageBox::question(this,"Delete chat?","Delete this conversation from this device?")!=QMessageBox::Yes)return;int n=index();if(n>=0)conversations.removeAt(n);ephemeral=false;save();newChat();}));bottom->addStretch();bottom->addWidget(icon("preferences-system","Settings and available features",[this]{settings();}));sv->addLayout(bottom);root->addWidget(sidebar);
  auto content=new QWidget;auto v=new QVBoxLayout(content);v->setContentsMargins(28,18,28,14);v->setSpacing(12);
  auto top=new QHBoxLayout;auto labels=new QVBoxLayout;title=new QLabel("New chat");title->setObjectName("role");model=new QLabel("Qwen3.5 0.8B · On this device");model->setObjectName("muted");labels->addWidget(title);labels->addWidget(model);top->addLayout(labels);top->addStretch();
  temporary=icon("view-private","Temporary chat — do not save history",[this]{newChat(temporary->isChecked());});temporary->setCheckable(true);top->addWidget(temporary);
  top->addWidget(icon("document-save","Export conversation",[this]{auto file=QFileDialog::getSaveFileName(this,"Export chat",QDir::homePath()+"/Nimbrel chat.md","Markdown (*.md)");if(file.isEmpty())return;QString text;for(auto m:chat()["messages"].toArray()){auto o=m.toObject();text+="## "+o["role"].toString()+"\n\n"+o["content"].toString()+"\n\n";}QSaveFile f(file);if(f.open(QIODevice::WriteOnly)){f.setPermissions(QFile::ReadOwner|QFile::WriteOwner);f.write(text.toUtf8());if(!f.commit())state->setText("Export failed");}}));
  top->addWidget(icon("weather-clear-night","Switch light or dark appearance",[this]{dark=!dark;theme();}));v->addLayout(top);
  scroll=new QScrollArea;scroll->setWidgetResizable(true);messages=new QWidget;cards=new QVBoxLayout(messages);cards->setSpacing(18);cards->setContentsMargins(0,0,8,0);scroll->setWidget(messages);v->addWidget(scroll,1);
  attachmentBox=new QWidget;auto av=new QVBoxLayout(attachmentBox);av->setContentsMargins(0,0,0,0);auto ar=new QHBoxLayout;ar->addWidget(new QLabel("Attachment preview · edit before sending"));ar->addStretch();ar->addWidget(icon("window-close","Remove attachment",[this]{attachment->clear();attachmentBox->hide();}));av->addLayout(ar);attachment=new QPlainTextEdit;attachment->setMaximumHeight(130);av->addWidget(attachment);v->addWidget(attachmentBox);attachmentBox->hide();
  input=new Composer;input->setPlaceholderText("Message Nimbrel");input->setAccessibleName("Message Nimbrel. Enter sends; Shift Enter starts a new line.");input->setMinimumHeight(76);input->setMaximumHeight(130);input->submit=[this]{ask();};v->addWidget(input);
  auto bar=new QHBoxLayout;bar->addWidget(icon("mail-attachment","Attach text, PDF or Word document",[this]{attach(QFileDialog::getOpenFileName(this,"Attach document",{},"Documents (*.txt *.md *.pdf *.docx *.log *.py *.cpp *.json *.csv);;All files (*)"));}));
  bar->addWidget(icon("utilities-system-monitor","Preview a read-only system summary",[this]{if(active)return;call({{"action","diagnostics"}},[this](QJsonObject r){if(r["ok"].toBool()){attachment->setPlainText(r["text"].toString());attachmentBox->show();mode->setCurrentIndex(6);}});}));
  mode=new QComboBox;const QList<QPair<QString,QString>> modes={{"Chat","chat"},{"Summarize","summarize"},{"Writing","rewrite"},{"Translate","translate"},{"Code","code"},{"Document","document"},{"System help","troubleshoot"},{"Plan","plan"},{"Study","study"}};for(auto m:modes)mode->addItem(m.first,m.second);mode->setToolTip("Choose how Nimbrel should help");bar->addWidget(mode);bar->addStretch();stop=icon("media-playback-stop","Stop response",[this]{if(active){active->setProperty("cancelled",true);active->kill();}});bar->addWidget(stop);send=icon("mail-send","Send message (Enter)",[this]{ask();});bar->addWidget(send);v->addLayout(bar);
  progress=new QProgressBar;progress->setRange(0,0);progress->hide();v->addWidget(progress);state=new QLabel("Starting local AI…");state->setObjectName("muted");state->setWordWrap(true);v->addWidget(state);privacy=new QLabel;privacy->setObjectName("muted");privacy->setAlignment(Qt::AlignCenter);v->addWidget(privacy);root->addWidget(content,1);setCentralWidget(central);theme();
  QFile f(storePath());if(f.open(QIODevice::ReadOnly)&&f.size()<32*1024*1024&&!QFileInfo(f).isSymLink()){auto doc=QJsonDocument::fromJson(f.readAll());if(doc.isArray())conversations=doc.array();}
  connect(search,&QLineEdit::textChanged,this,[this]{list();});connect(chats,&QListWidget::itemClicked,this,[this](QListWidgetItem *item){if(active)return;current=item->data(Qt::UserRole).toString();ephemeral=chat()["temporary"].toBool();temporary->setChecked(ephemeral);input->clear();attachmentBox->hide();attachment->clear();render();});
  connect(new QShortcut(QKeySequence("Ctrl+Return"),this),&QShortcut::activated,this,[this]{ask();});
  connect(new QShortcut(QKeySequence("Ctrl+N"),this),&QShortcut::activated,this,[this]{newChat();});
  newChat();busy(false);input->setFocus();connect(&statusTimer,&QTimer::timeout,this,[this]{if(!active)refresh();});statusTimer.start(10000);QTimer::singleShot(0,this,[this]{refresh();});
  auto args=QCoreApplication::arguments();if(args.size()>2&&args[1]=="--ask")input->setPlainText(args.mid(2).join(" "));if(args.size()>2&&args[1]=="--file")QTimer::singleShot(2000,this,[this,args]{attach(args[2]);});
 }
 ~Nimbrel() override {if(active){active->disconnect(this);active->kill();active->waitForFinished(1500);}}
};
int main(int argc,char **argv){QApplication app(argc,argv);app.setApplicationName("Nimbrel");app.setOrganizationName("Aether");Nimbrel window;window.show();return app.exec();}
