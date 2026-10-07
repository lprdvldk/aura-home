#include "ClimateChart.hpp"

#include <QChart>
#include <QDateTime>
#include <QDateTimeAxis>
#include <QLineSeries>
#include <QPainter>
#include <QValueAxis>
#include <algorithm>

ClimateChart::ClimateChart(QWidget* parent) : QChartView(parent) {
  chart_ = new QChart();
  chart_->setBackgroundBrush(QColor(QStringLiteral("#171d28")));
  chart_->setPlotAreaBackgroundBrush(QColor(QStringLiteral("#171d28")));
  chart_->setPlotAreaBackgroundVisible(true);
  chart_->setTitleBrush(QBrush(QColor(QStringLiteral("#e8eef8"))));
  chart_->legend()->setLabelColor(QColor(QStringLiteral("#e8eef8")));
  chart_->setAnimationOptions(QChart::NoAnimation);

  primary_ = new QLineSeries();
  secondary_ = new QLineSeries();
  primary_->setColor(QColor(QStringLiteral("#f0a36a")));
  secondary_->setColor(QColor(QStringLiteral("#6ec8c0")));
  chart_->addSeries(primary_);
  chart_->addSeries(secondary_);

  axisX_ = new QDateTimeAxis();
  axisX_->setFormat(QStringLiteral("hh:mm:ss"));
  axisX_->setLabelsColor(QColor(QStringLiteral("#93a0b5")));
  axisX_->setGridLineColor(QColor(QStringLiteral("#2a3344")));
  axisY_ = new QValueAxis();
  axisY_->setLabelsColor(QColor(QStringLiteral("#f0a36a")));
  axisY_->setGridLineColor(QColor(QStringLiteral("#2a3344")));
  axisY2_ = new QValueAxis();
  axisY2_->setLabelsColor(QColor(QStringLiteral("#6ec8c0")));
  axisY2_->setGridLineColor(Qt::transparent);

  chart_->addAxis(axisX_, Qt::AlignBottom);
  chart_->addAxis(axisY_, Qt::AlignLeft);
  chart_->addAxis(axisY2_, Qt::AlignRight);
  primary_->attachAxis(axisX_);
  primary_->attachAxis(axisY_);
  secondary_->attachAxis(axisX_);
  secondary_->attachAxis(axisY2_);

  setChart(chart_);
  setRenderHint(QPainter::Antialiasing);
  setObjectName(QStringLiteral("chartCard"));
}

void ClimateChart::setSamples(const QString& kind, const QVector<SensorSample>& samples) {
  primary_->clear();
  secondary_->clear();
  const bool air = kind == QLatin1String("air_quality");
  primary_->setName(air ? QStringLiteral("PM2.5 µg/m³") : QStringLiteral("Temperature °C"));
  secondary_->setName(air ? QStringLiteral("CO₂ ppm") : QStringLiteral("Humidity %"));
  axisY_->setTitleText(air ? QStringLiteral("µg/m³") : QStringLiteral("°C"));
  axisY2_->setTitleText(air ? QStringLiteral("ppm") : QStringLiteral("% RH"));
  axisY_->setTitleBrush(QBrush(QColor(air ? QStringLiteral("#9b8cff") : QStringLiteral("#f0a36a"))));
  axisY2_->setTitleBrush(QBrush(QColor(air ? QStringLiteral("#c9b37a") : QStringLiteral("#6ec8c0"))));
  primary_->setColor(QColor(air ? QStringLiteral("#9b8cff") : QStringLiteral("#f0a36a")));
  secondary_->setColor(QColor(air ? QStringLiteral("#c9b37a") : QStringLiteral("#6ec8c0")));

  qint64 minX = 0;
  qint64 maxX = 0;
  double minY = 0;
  double maxY = 1;
  double minY2 = 0;
  double maxY2 = 1;
  bool any = false;
  for (const auto& sample : samples) {
    const auto left = sample.metric(air ? QStringLiteral("pm25_ugm3") : QStringLiteral("temperature_c"));
    const auto right = sample.metric(air ? QStringLiteral("co2_ppm") : QStringLiteral("humidity_pct"));
    const auto x = sample.unixMs;
    if (left) {
      primary_->append(static_cast<qreal>(x), *left);
      minY = any ? std::min(minY, *left) : *left;
      maxY = any ? std::max(maxY, *left) : *left;
    }
    if (right) {
      secondary_->append(static_cast<qreal>(x), *right);
      minY2 = any ? std::min(minY2, *right) : *right;
      maxY2 = any ? std::max(maxY2, *right) : *right;
    }
    if (left || right) {
      if (!any) {
        minX = maxX = x;
        any = true;
      } else {
        minX = std::min(minX, x);
        maxX = std::max(maxX, x);
      }
    }
  }
  if (!any) {
    const auto now = QDateTime::currentMSecsSinceEpoch();
    axisX_->setRange(QDateTime::fromMSecsSinceEpoch(now - 30'000), QDateTime::fromMSecsSinceEpoch(now));
    return;
  }
  if (minX == maxX) maxX += 1000;
  axisX_->setRange(QDateTime::fromMSecsSinceEpoch(minX), QDateTime::fromMSecsSinceEpoch(maxX));
  axisY_->setRange(minY - 1.0, maxY + 1.0);
  axisY2_->setRange(minY2 - 5.0, maxY2 + 5.0);
}
