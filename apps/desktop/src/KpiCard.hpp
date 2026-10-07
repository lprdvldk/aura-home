#pragma once

#include <QFrame>

class QLabel;

class KpiCard : public QFrame {
  Q_OBJECT
 public:
  KpiCard(const QString& title, const QString& valueObjectName, QWidget* parent = nullptr);
  void setValue(const QString& text);

 private:
  QLabel* value_{};
};
