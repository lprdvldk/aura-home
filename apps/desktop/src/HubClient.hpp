#pragma once

#include "Types.hpp"

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QUrl>
#include <QVector>

class QNetworkAccessManager;
class QWebSocket;

class HubClient : public QObject {
  Q_OBJECT
 public:
  explicit HubClient(QObject* parent = nullptr);

  void connectToHub(const QString& host, quint16 port);
  void disconnectFromHub();
  bool isConnected() const;
  QUrl httpBase() const { return httpBase_; }

 public slots:
  void setDeviceEnabled(const QString& deviceId, bool enabled);

 signals:
  void connectionChanged(bool connected, const QString& detail);
  void snapshotReceived(const QString& houseName, const QVector<DeviceInfo>& devices,
                        const QHash<QString, SensorSample>& latest, const QVector<AlertInfo>& alerts);
  void sampleReceived(const SensorSample& sample, const DeviceInfo& device);
  void alertReceived(const AlertInfo& alert);
  void errorReceived(const QString& message);

 private:
  void openSocket();
  void handleText(const QString& text);
  SensorSample parseSample(const QJsonObject& obj) const;
  DeviceInfo parseDevice(const QJsonObject& obj) const;
  AlertInfo parseAlert(const QJsonObject& obj) const;

  QWebSocket* socket_{};
  QNetworkAccessManager* http_{};
  QUrl httpBase_;
  QUrl wsUrl_;
  bool wantConnected_{false};
};
