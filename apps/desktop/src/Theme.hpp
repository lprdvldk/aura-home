#pragma once

#include <QString>

inline QString houseStylesheet() {
  return QStringLiteral(R"(
    QMainWindow, QWidget#central { background: #10141c; color: #e8eef8; }
    QLabel { color: #e8eef8; }
    QLabel[muted="true"] { color: #93a0b5; }
    QCheckBox { color: #e8eef8; spacing: 6px; }
    QLineEdit, QSpinBox {
      background: #1d2533; color: #e8eef8; border: 1px solid #2a3344;
      border-radius: 8px; padding: 6px 8px; selection-background-color: #3d4d68;
    }
    QPushButton {
      background: #2b3648; color: #e8eef8; border: 1px solid #3a465c;
      border-radius: 8px; padding: 7px 14px;
    }
    QPushButton:hover { background: #354257; }
    QPushButton:disabled { color: #6d7a8d; }
    QPushButton#primary { background: #3d6b6a; border-color: #4e8583; }
    QTreeWidget {
      background: #171d28; border: none; color: #e8eef8;
      outline: none;
    }
    QTreeWidget::item { padding: 8px 6px; }
    QTreeWidget::item:selected { background: #243044; }
    QHeaderView::section { background: #171d28; color: #93a0b5; border: none; padding: 6px; }
    QFrame#card, QFrame#chartCard {
      background: #171d28; border: 1px solid #2a3344; border-radius: 14px;
    }
    QFrame#alertBar {
      background: #2a2230; border: 1px solid #4a3948; border-radius: 10px; color: #f0d4d4;
    }
    QLabel#kpiValue { font-size: 28px; font-weight: 650; }
    QLabel#kpiTemp { color: #f0a36a; font-size: 28px; font-weight: 650; }
    QLabel#kpiHum { color: #6ec8c0; font-size: 28px; font-weight: 650; }
    QLabel#kpiAir { color: #9b8cff; font-size: 28px; font-weight: 650; }
    QStatusBar { background: #10141c; color: #93a0b5; }
  )");
}
