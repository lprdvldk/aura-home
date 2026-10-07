#include "HubClient.hpp"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QTimer>
#include <QWebSocket>

HubClient::HubClient(QObject* parent) : QObject(parent) {
  socket_ = new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this);
  http_ = new QNetworkAccessManager(this);
  connect(socket_, &QWebSocket::connected, this, [this] {
    emit connectionChanged(true, QStringLiteral("Live telemetry"));
  });
  connect(socket_, &QWebSocket::disconnected, this, [this] {
    emit connectionChanged(false, QStringLiteral("Disconnected"));
    if (wantConnected_) {
      QTimer::singleShot(1200, this, [this] {
        if (wantConnected_) openSocket();
      });
    }
  });
  connect(socket_, &QWebSocket::textMessageReceived, this, &HubClient::handleText);
  connect(socket_, &QWebSocket::errorOccurred, this, [this](QAbstractSocket::SocketError) {
    emit errorReceived(socket_->errorString());
  });
}

void HubClient::connectToHub(const QString& host, quint16 port) {
  httpBase_ = QUrl(QStringLiteral("http://%1:%2").arg(host).arg(port));
  wsUrl_ = QUrl(QStringLiteral("ws://%1:%2/v1/telemetry").arg(host).arg(port));
  wantConnected_ = true;
  openSocket();
}

void HubClient::disconnectFromHub() {
  wantConnected_ = false;
  socket_->close();
}

bool HubClient::isConnected() const {
  return socket_->state() == QAbstractSocket::ConnectedState;
}

void HubClient::setDeviceEnabled(const QString& deviceId, bool enabled) {
  QUrl url(httpBase_);
  url.setPath(QStringLiteral("/v1/devices/%1/enabled").arg(deviceId));
  QNetworkRequest req(url);
  req.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
  const auto body = QJsonDocument(QJsonObject{{QStringLiteral("enabled"), enabled}}).toJson(QJsonDocument::Compact);
  http_->post(req, body);
}

void HubClient::openSocket() {
  if (socket_->state() == QAbstractSocket::ConnectedState ||
      socket_->state() == QAbstractSocket::ConnectingState) {
    socket_->close();
  }
  emit connectionChanged(false, QStringLiteral("Connecting…"));
  socket_->open(wsUrl_);
}

SensorSample HubClient::parseSample(const QJsonObject& obj) const {
  SensorSample sample;
  sample.deviceId = obj.value(QStringLiteral("device_id")).toString();
  sample.unixMs = obj.value(QStringLiteral("unix_ms")).toVariant().toLongLong();
  sample.errorCode = obj.value(QStringLiteral("error_code")).toInt();
  sample.errorMessage = obj.value(QStringLiteral("error_message")).toString();
  sample.source = obj.value(QStringLiteral("source")).toString();
  for (const auto& value : obj.value(QStringLiteral("metrics")).toArray()) {
    const auto m = value.toObject();
    sample.metrics.push_back(MetricPoint{
        m.value(QStringLiteral("name")).toString(),
        m.value(QStringLiteral("value")).toDouble(),
        m.value(QStringLiteral("unit")).toString(),
    });
  }
  return sample;
}

DeviceInfo HubClient::parseDevice(const QJsonObject& obj) const {
  DeviceInfo device;
  device.id = obj.value(QStringLiteral("id")).toString();
  device.name = obj.value(QStringLiteral("name")).toString();
  device.room = obj.value(QStringLiteral("room")).toString();
  device.kind = obj.value(QStringLiteral("kind")).toString();
  device.status = obj.value(QStringLiteral("status")).toString();
  device.driver = obj.value(QStringLiteral("driver")).toString();
  device.enabled = obj.value(QStringLiteral("enabled")).toBool(true);
  return device;
}

AlertInfo HubClient::parseAlert(const QJsonObject& obj) const {
  AlertInfo alert;
  alert.id = obj.value(QStringLiteral("id")).toString();
  alert.deviceId = obj.value(QStringLiteral("device_id")).toString();
  alert.metric = obj.value(QStringLiteral("metric")).toString();
  alert.message = obj.value(QStringLiteral("message")).toString();
  alert.severity = obj.value(QStringLiteral("severity")).toString();
  alert.unixMs = obj.value(QStringLiteral("unix_ms")).toVariant().toLongLong();
  return alert;
}

void HubClient::handleText(const QString& text) {
  const auto doc = QJsonDocument::fromJson(text.toUtf8());
  if (!doc.isObject()) return;
  const auto obj = doc.object();
  const auto type = obj.value(QStringLiteral("type")).toString();
  if (type == QLatin1String("snapshot")) {
    QVector<DeviceInfo> devices;
    for (const auto& value : obj.value(QStringLiteral("devices")).toArray()) {
      devices.push_back(parseDevice(value.toObject()));
    }
    QHash<QString, SensorSample> latest;
    const auto latestObj = obj.value(QStringLiteral("latest")).toObject();
    for (auto it = latestObj.begin(); it != latestObj.end(); ++it) {
      latest.insert(it.key(), parseSample(it.value().toObject()));
    }
    QVector<AlertInfo> alerts;
    for (const auto& value : obj.value(QStringLiteral("alerts")).toArray()) {
      alerts.push_back(parseAlert(value.toObject()));
    }
    emit snapshotReceived(obj.value(QStringLiteral("house_name")).toString(), devices, latest, alerts);
  } else if (type == QLatin1String("sample")) {
    emit sampleReceived(parseSample(obj.value(QStringLiteral("sample")).toObject()),
                        parseDevice(obj.value(QStringLiteral("device")).toObject()));
  } else if (type == QLatin1String("alert")) {
    emit alertReceived(parseAlert(obj.value(QStringLiteral("alert")).toObject()));
  }
}
