#pragma once

#include "Types.hpp"

#include <QChartView>
#include <QVector>

class QChart;
class QDateTimeAxis;
class QLineSeries;
class QValueAxis;

class ClimateChart : public QChartView {
  Q_OBJECT
 public:
  explicit ClimateChart(QWidget* parent = nullptr);
  void setSamples(const QString& kind, const QVector<SensorSample>& samples);

 private:
  QChart* chart_{};
  QLineSeries* primary_{};
  QLineSeries* secondary_{};
  QDateTimeAxis* axisX_{};
  QValueAxis* axisY_{};
  QValueAxis* axisY2_{};
};
