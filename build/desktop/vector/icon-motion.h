// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QAbstractItemView>
#include <QApplication>
#include <QPainter>
#include <QPersistentModelIndex>
#include <QSettings>
#include <QStandardPaths>
#include <QStyledItemDelegate>
#include <QVariantAnimation>
#include <algorithm>

// Animate only the decoration; labels, selection, focus and hit targets stay put.
class IconMotion : public QStyledItemDelegate {
public:
    explicit IconMotion(QAbstractItemView *view) : QStyledItemDelegate(view), view(view) {
        motion.setStartValue(1.0);
        motion.setKeyValueAt(0.3, 0.82);
        motion.setEndValue(1.0);
        motion.setEasingCurve(QEasingCurve::InOutCubic);
        connect(&motion, &QVariantAnimation::valueChanged, this, [this](const QVariant &value) {
            scale = value.toReal();
            if (active.isValid()) this->view->viewport()->update(this->view->visualRect(active));
        });
        connect(view, &QAbstractItemView::clicked, this, &IconMotion::pulse);
        connect(view, &QAbstractItemView::activated, this, &IconMotion::pulse);
    }

    void pulse(const QModelIndex &index) {
        motion.stop();
        if (active.isValid()) view->viewport()->update(view->visualRect(active));
        active = QPersistentModelIndex();
        scale = 1.0;
        QSettings settings(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
                           + "/kdeglobals", QSettings::IniFormat);
        const double factor = settings.value("KDE/AnimationDurationFactor", 1.0).toDouble();
        if (factor <= 0 || !index.isValid() || !(index.flags() & Qt::ItemIsEnabled)
            || index.data(Qt::DecorationRole).value<QIcon>().isNull()) return;
        active = index;
        motion.setDuration(std::clamp(int(220 * std::clamp(factor, 0.1, 4.0)), 22, 880));
        motion.start();
    }

    void paint(QPainter *painter, const QStyleOptionViewItem &option,
               const QModelIndex &index) const override {
        QStyleOptionViewItem item(option);
        initStyleOption(&item, index);
        if (index == active && scale < 0.999 && !item.icon.isNull()) {
            const auto mode = !(item.state & QStyle::State_Enabled) ? QIcon::Disabled
                : (item.state & QStyle::State_Selected) ? QIcon::Selected : QIcon::Normal;
            const auto state = (item.state & QStyle::State_Open) ? QIcon::On : QIcon::Off;
            const qreal dpr = view->devicePixelRatioF();
            QPixmap canvas(item.decorationSize * dpr);
            canvas.setDevicePixelRatio(dpr);
            canvas.fill(Qt::transparent);
            QPainter iconPainter(&canvas);
            iconPainter.setRenderHint(QPainter::SmoothPixmapTransform);
            const QSize size = item.decorationSize * scale;
            const QRect rect(QPoint((item.decorationSize.width() - size.width()) / 2,
                                    (item.decorationSize.height() - size.height()) / 2), size);
            item.icon.paint(&iconPainter, rect, Qt::AlignCenter, mode, state);
            iconPainter.end();
            QIcon animated;
            animated.addPixmap(canvas, mode, state);
            item.icon = animated;
        }
        const QStyle *style = item.widget ? item.widget->style() : QApplication::style();
        style->drawControl(QStyle::CE_ItemViewItem, &item, painter, item.widget);
    }
private:
    QAbstractItemView *view;
    QVariantAnimation motion;
    QPersistentModelIndex active;
    qreal scale = 1.0;
};
