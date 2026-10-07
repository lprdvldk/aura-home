#include "KpiCard.hpp"

#include <QLabel>
#include <QVBoxLayout>

KpiCard::KpiCard(const QString& title, const QString& valueObjectName, QWidget* parent) : QFrame(parent) {
  setObjectName(QStringLiteral("card"));
  auto* layout = new QVBoxLayout(this);
  auto* label = new QLabel(title);
  label->setProperty("muted", true);
  value_ = new QLabel(QStringLiteral("—"));
  value_->setObjectName(valueObjectName);
  layout->addWidget(label);
  layout->addWidget(value_);
}

void KpiCard::setValue(const QString& text) {
  value_->setText(text);
}
