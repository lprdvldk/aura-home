#include "MainWindow.hpp"

#include "ClimateChart.hpp"
#include "HubClient.hpp"
#include "KpiCard.hpp"
#include "TelemetryStore.hpp"
#include "Theme.hpp"

#include <QCheckBox>
#include <QDesktopServices>
#include <QFrame>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QSplitter>
#include <QStatusBar>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QUrl>
#include <QVBoxLayout>
#include <cmath>
#include <optional>

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
  setWindowTitle(QStringLiteral("Smart House"));
  resize(1180, 740);
  setStyleSheet(houseStylesheet());

  client_ = new HubClient(this);
  store_ = new TelemetryStore(this);

  auto* central = new QWidget;
  central->setObjectName(QStringLiteral("central"));
  setCentralWidget(central);
  auto* root = new QVBoxLayout(central);

  auto* top = new QHBoxLayout;
  auto* titleBox = new QVBoxLayout;
  auto* title = new QLabel(QStringLiteral("Smart House"));
  title->setStyleSheet(QStringLiteral("font-size: 20px; font-weight: 650;"));
  auto* subtitle = new QLabel(QStringLiteral("Pulls live sensors from the house hub over TLS WebSocket"));
  subtitle->setProperty("muted", true);
  titleBox->addWidget(title);
  titleBox->addWidget(subtitle);

  host_ = new QLineEdit(QStringLiteral("127.0.0.1"));
  port_ = new QSpinBox;
  port_->setRange(1, 65535);
  port_->setValue(18443);
  viewerToken_ = new QLineEdit;
  viewerToken_->setPlaceholderText(QStringLiteral("viewer token"));
  viewerToken_->setEchoMode(QLineEdit::Password);
  viewerToken_->setMinimumWidth(140);
  tls_ = new QCheckBox(QStringLiteral("TLS"));
  allowSelfSigned_ = new QCheckBox(QStringLiteral("Trust self-signed"));
  auto* connectBtn = new QPushButton(QStringLiteral("Connect"));
  connectBtn->setObjectName(QStringLiteral("primary"));
  auto* disconnectBtn = new QPushButton(QStringLiteral("Disconnect"));
  auto* accountBtn = new QPushButton(QStringLiteral("Account"));
  connection_ = new QLabel(QStringLiteral("Disconnected"));
  connection_->setProperty("muted", true);

  top->addLayout(titleBox, 1);
  top->addWidget(new QLabel(QStringLiteral("Hub")));
  top->addWidget(host_);
  top->addWidget(port_);
  top->addWidget(viewerToken_);
  top->addWidget(tls_);
  top->addWidget(allowSelfSigned_);
  top->addWidget(connectBtn);
  top->addWidget(disconnectBtn);
  top->addWidget(accountBtn);
  top->addWidget(connection_);
  root->addLayout(top);

  alert_ = new QLabel;
  alert_->setObjectName(QStringLiteral("alertBar"));
  alert_->setWordWrap(true);
  alert_->hide();
  root->addWidget(alert_);

  auto* splitter = new QSplitter;
  tree_ = new QTreeWidget;
  tree_->setHeaderHidden(true);
  tree_->setMinimumWidth(240);
  splitter->addWidget(tree_);

  auto* right = new QWidget;
  auto* rightLayout = new QVBoxLayout(right);
  rightLayout->setContentsMargins(8, 0, 0, 0);

  auto* kpis = new QHBoxLayout;
  temp_ = new KpiCard(QStringLiteral("Temperature"), QStringLiteral("kpiTemp"));
  humidity_ = new KpiCard(QStringLiteral("Humidity"), QStringLiteral("kpiHum"));
  pm_ = new KpiCard(QStringLiteral("PM2.5"), QStringLiteral("kpiAir"));
  co2_ = new KpiCard(QStringLiteral("CO₂"), QStringLiteral("kpiAir"));
  kpis->addWidget(temp_);
  kpis->addWidget(humidity_);
  kpis->addWidget(pm_);
  kpis->addWidget(co2_);
  rightLayout->addLayout(kpis);

  chart_ = new ClimateChart;
  chart_->setMinimumHeight(320);
  rightLayout->addWidget(chart_, 1);

  empty_ = new QLabel(QStringLiteral("Connect to the local hub to see live climate charts."));
  empty_->setAlignment(Qt::AlignCenter);
  empty_->setProperty("muted", true);
  empty_->setStyleSheet(
      QStringLiteral("border: 1px dashed #2a3344; border-radius: 14px; padding: 24px; color: #93a0b5;"));
  rightLayout->addWidget(empty_);

  splitter->addWidget(right);
  splitter->setStretchFactor(1, 1);
  root->addWidget(splitter, 1);

  connect(connectBtn, &QPushButton::clicked, this, [this] {
    client_->connectToHub(host_->text().trimmed(), static_cast<quint16>(port_->value()),
                          viewerToken_->text(), tls_->isChecked(), allowSelfSigned_->isChecked());
  });
  connect(disconnectBtn, &QPushButton::clicked, client_, &HubClient::disconnectFromHub);
  connect(accountBtn, &QPushButton::clicked, this, [this] {
    const auto scheme = tls_->isChecked() ? QStringLiteral("https") : QStringLiteral("http");
    const auto url =
        QStringLiteral("%1://%2:%3/account/login").arg(scheme, host_->text().trimmed()).arg(port_->value());
    QDesktopServices::openUrl(QUrl(url));
  });
  connect(client_, &HubClient::connectionChanged, this, [this](bool ok, const QString& detail) {
    connection_->setText(detail);
    connection_->setStyleSheet(ok ? QStringLiteral("color: #7dcea0;") : QStringLiteral("color: #e7b549;"));
    if (!ok) empty_->setText(QStringLiteral("Waiting for the hub on WebSocket /v1/telemetry …"));
  });
  connect(client_, &HubClient::errorReceived, this, [this](const QString& message) {
    empty_->show();
    empty_->setText(QStringLiteral("Could not reach the hub: %1").arg(message));
  });
  connect(client_, &HubClient::snapshotReceived, store_, &TelemetryStore::applySnapshot);
  connect(client_, &HubClient::sampleReceived, store_, &TelemetryStore::applySample);
  connect(client_, &HubClient::alertReceived, store_, &TelemetryStore::applyAlert);
  connect(store_, &TelemetryStore::changed, this, &MainWindow::refresh);
  connect(tree_, &QTreeWidget::currentItemChanged, this, [this](QTreeWidgetItem* item) {
    if (item && !item->data(0, Qt::UserRole).toString().isEmpty()) {
      store_->setSelectedId(item->data(0, Qt::UserRole).toString());
    }
  });

  statusBar()->showMessage(QStringLiteral("gRPC hub :18551 · WebSocket telemetry :18443"));
}

void MainWindow::rebuildDeviceTree() {
  const auto selected = store_->selectedId();
  tree_->clear();
  QHash<QString, QTreeWidgetItem*> rooms;
  QTreeWidgetItem* selectItem = nullptr;
  for (const auto& device : store_->devices()) {
    auto* room = rooms.value(device.room);
    if (!room) {
      room = new QTreeWidgetItem(tree_, {device.room});
      room->setFlags(room->flags() & ~Qt::ItemIsSelectable);
      rooms.insert(device.room, room);
    }
    auto* item = new QTreeWidgetItem(room, {QStringLiteral("%1  ·  %2").arg(device.name, device.status)});
    item->setData(0, Qt::UserRole, device.id);
    if (device.id == selected) selectItem = item;
  }
  tree_->expandAll();
  if (selectItem) tree_->setCurrentItem(selectItem);
}

void MainWindow::refresh() {
  setWindowTitle(store_->houseName());
  QString fingerprint;
  for (const auto& device : store_->devices()) {
    fingerprint += device.id + device.status + (device.enabled ? QLatin1Char('1') : QLatin1Char('0'));
  }
  if (fingerprint != treeFingerprint_) {
    treeFingerprint_ = fingerprint;
    rebuildDeviceTree();
  }
  temp_->setValue(formatMetric(store_->houseMetric(QStringLiteral("temperature_c")), QStringLiteral("°")));
  humidity_->setValue(formatMetric(store_->houseMetric(QStringLiteral("humidity_pct")), QStringLiteral("%")));
  pm_->setValue(formatMetric(store_->houseMetric(QStringLiteral("pm25_ugm3")), QStringLiteral(" µg")));
  co2_->setValue(formatMetric(store_->houseMetric(QStringLiteral("co2_ppm")), QStringLiteral(" ppm")));

  const auto selected = store_->selectedId();
  const auto device = store_->device(selected);
  chart_->setSamples(device.kind, store_->history(selected));
  empty_->setVisible(store_->devices().isEmpty());
  if (!store_->alerts().isEmpty()) {
    alert_->setText(store_->alerts().front().message);
    alert_->show();
  } else {
    alert_->hide();
  }
}

QString MainWindow::formatMetric(std::optional<double> value, const QString& suffix) {
  if (!value) return QStringLiteral("—");
  return QStringLiteral("%1%2").arg(*value, 0, 'f', (*value == std::floor(*value)) ? 0 : 1).arg(suffix);
}
