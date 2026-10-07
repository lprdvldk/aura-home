#pragma once

#include "Types.hpp"

#include <QHash>
#include <QObject>
#include <QVector>
#include <deque>

class TelemetryStore : public QObject {
  Q_OBJECT
 public:
  explicit TelemetryStore(QObject* parent = nullptr);

  void applySnapshot(const QString& houseName, const QVector<DeviceInfo>& devices,
                     const QHash<QString, SensorSample>& latest, const QVector<AlertInfo>& alerts);
  void applySample(const SensorSample& sample, const DeviceInfo& device);
  void applyAlert(const AlertInfo& alert);
  void clear();

  QString houseName() const { return houseName_; }
  QString selectedId() const { return selectedId_; }
  void setSelectedId(const QString& id);
  QVector<DeviceInfo> devices() const { return devices_.values(); }
  DeviceInfo device(const QString& id) const { return devices_.value(id); }
  SensorSample latest(const QString& id) const { return latest_.value(id); }
  std::optional<double> houseMetric(const QString& name) const;
  QVector<SensorSample> history(const QString& id) const;
  QVector<AlertInfo> alerts() const { return alerts_; }

 signals:
  void changed();

 private:
  QString houseName_{QStringLiteral("Smart House")};
  QString selectedId_;
  QHash<QString, DeviceInfo> devices_;
  QHash<QString, SensorSample> latest_;
  QHash<QString, std::deque<SensorSample>> history_;
  QVector<AlertInfo> alerts_;
};
