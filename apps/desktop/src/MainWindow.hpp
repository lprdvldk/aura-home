#pragma once

#include <QMainWindow>

class ClimateChart;
class HubClient;
class KpiCard;
class QLabel;
class QLineEdit;
class QSpinBox;
class QTreeWidget;
class TelemetryStore;

class MainWindow : public QMainWindow {
  Q_OBJECT
 public:
  explicit MainWindow(QWidget* parent = nullptr);

 private:
  void rebuildDeviceTree();
  void refresh();
  static QString formatMetric(std::optional<double> value, const QString& suffix);

  HubClient* client_{};
  TelemetryStore* store_{};
  QLineEdit* host_{};
  QSpinBox* port_{};
  QLabel* connection_{};
  QLabel* empty_{};
  QLabel* alert_{};
  QTreeWidget* tree_{};
  QString treeFingerprint_;
  KpiCard* temp_{};
  KpiCard* humidity_{};
  KpiCard* pm_{};
  KpiCard* co2_{};
  ClimateChart* chart_{};
};
