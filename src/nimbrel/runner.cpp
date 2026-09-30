#include <KRunner/AbstractRunner>
#include <KRunner/RunnerContext>
#include <KRunner/QueryMatch>
#include <KPluginFactory>
#include <QProcess>
#include <QIcon>
class NimbrelRunner : public KRunner::AbstractRunner {
    Q_OBJECT
public:
    NimbrelRunner(QObject *parent,const KPluginMetaData &data):KRunner::AbstractRunner(parent,data) {}
    void match(KRunner::RunnerContext &context) override {
        const QString query=context.query().trimmed();
        QString question;
        if(query.startsWith("ai ",Qt::CaseInsensitive))question=query.mid(3).trimmed();
        else if(query.startsWith("nimbrel ",Qt::CaseInsensitive))question=query.mid(8).trimmed();
        else return;
        if(question.isEmpty()||question.size()>6000)return;
        KRunner::QueryMatch match(this);match.setId("nimbrel");match.setText("Ask Nimbrel: "+question);
        match.setSubtext("Open your self-hosted AI workspace · review before sending");
        match.setIcon(QIcon::fromTheme("org.aether.Nimbrel"));match.setRelevance(1.0);match.setData(question);context.addMatch(match);
    }
    void run(const KRunner::RunnerContext &,const KRunner::QueryMatch &match) override {
        QProcess::startDetached("/usr/bin/nimbrel",{"--ask",match.data().toString()});
    }
};
K_PLUGIN_CLASS_WITH_JSON(NimbrelRunner,"runner.json")
#include "runner.moc"
