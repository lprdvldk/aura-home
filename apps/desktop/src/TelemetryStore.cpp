#include "TelemetryStore.hpp"

TelemetryStore::TelemetryStore(QObject* parent) : QObject(parent) {}

void TelemetryStore::applySnapshot(const QString& houseName, const QVector<DeviceInfo>& devices,
                                   const QHash<QString, SensorSample>& latest,
                                   const QVector<AlertInfo>& alerts) {
  houseName_ = houseName.isEmpty() ? QStringLiteral("Smart House") : houseName;
  devices_.clear();
  for (const auto& device : devices) devices_.insert(device.id, device);
  latest_ = latest;
  history_.clear();
  for (auto it = latest.begin(); it != latest.end(); ++it) {
    history_[it.key()].push_back(it.value());
  }
  alerts_ = alerts;
  if (selectedId_.isEmpty() || !devices_.contains(selectedId_)) {
    selectedId_.clear();
    for (const auto& device : devices) {
      if (device.kind == QLatin1String("climate")) {
        selectedId_ = device.id;
        break;
      }
    }
    if (selectedId_.isEmpty() && !devices.isEmpty()) selectedId_ = devices.front().id;
  }
  emit changed();
}

void TelemetryStore::applySample(const SensorSample& sample, const DeviceInfo& device) {
  if (!device.id.isEmpty()) devices_.insert(device.id, device);
  latest_.insert(sample.deviceId, sample);
  auto& hist = history_[sample.deviceId];
  hist.push_back(sample);
  while (hist.size() > 240) hist.pop_front();
  emit changed();
}

void TelemetryStore::applyAlert(const AlertInfo& alert) {
  alerts_.prepend(alert);
  while (alerts_.size() > 20) alerts_.removeLast();
  emit changed();
}

void TelemetryStore::clear() {
  devices_.clear();
  latest_.clear();
  history_.clear();
  alerts_.clear();
  selectedId_.clear();
  emit changed();
}

void TelemetryStore::setSelectedId(const QString& id) {
  if (selectedId_ == id) return;
  selectedId_ = id;
  emit changed();
}

std::optional<double> TelemetryStore::houseMetric(const QString& name) const {
  if (!selectedId_.isEmpty()) {
    if (const auto value = latest_.value(selectedId_).metric(name)) return value;
  }
  std::optional<double> found;
  for (const auto& sample : latest_) {
    if (const auto value = sample.metric(name)) found = value;
  }
  return found;
}

QVector<SensorSample> TelemetryStore::history(const QString& id) const {
  QVector<SensorSample> out;
  const auto it = history_.constFind(id);
  if (it == history_.cend()) return out;
  out.reserve(static_cast<int>(it->size()));
  for (const auto& sample : *it) out.push_back(sample);
  return out;
}
