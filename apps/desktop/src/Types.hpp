#pragma once

#include <QHash>
#include <QString>
#include <QVector>
#include <cstdint>
#include <optional>

struct MetricPoint {
  QString name;
  double value{};
  QString unit;
};

struct SensorSample {
  QString deviceId;
  qint64 unixMs{};
  QVector<MetricPoint> metrics;
  int errorCode{};
  QString errorMessage;
  QString source;
  std::optional<double> metric(const QString& name) const {
    for (const auto& m : metrics) {
      if (m.name == name) return m.value;
    }
    return std::nullopt;
  }
};

struct DeviceInfo {
  QString id;
  QString name;
  QString room;
  QString kind;
  QString status;
  QString driver;
  bool enabled{true};
};

struct AlertInfo {
  QString id;
  QString deviceId;
  QString metric;
  QString message;
  QString severity;
  qint64 unixMs{};
};
