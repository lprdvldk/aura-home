#include "MainWindow.hpp"

#include <QApplication>

int main(int argc, char* argv[]) {
  QApplication app(argc, argv);
  app.setApplicationName(QStringLiteral("Smart House"));
  app.setOrganizationName(QStringLiteral("SmartHouse"));
  app.setStyle(QStringLiteral("Fusion"));

  MainWindow window;
  window.show();
  return app.exec();
}
