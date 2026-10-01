#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QSvgRenderer>
int main(int argc,char **argv){QGuiApplication app(argc,argv);if(argc!=3 && argc!=4)return 2;int size=argc==4?QString::fromLocal8Bit(argv[3]).toInt():192;if(size<1||size>4096)return 2;QSvgRenderer svg(QString::fromLocal8Bit(argv[1]));if(!svg.isValid())return 3;QImage image(size,size,QImage::Format_ARGB32_Premultiplied);image.fill(Qt::transparent);QPainter p(&image);svg.render(&p);p.end();return image.save(QString::fromLocal8Bit(argv[2]))?0:4;}
