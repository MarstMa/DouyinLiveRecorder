"""现代深色主题（QSS）。"""

LIGHT_BLUE_QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #E5E7EB;
}

QMainWindow { background-color: #0F172A; }
QDialog { background-color: #0F172A; }

/* ---------- 卡片 ---------- */
QFrame#card {
    background-color: #1E293B;
    border: 1px solid #2A3A52;
    border-radius: 12px;
}

QFrame#tileCard {
    background-color: #1E293B;
    border: 1px solid #2A3A52;
    border-radius: 14px;
}
QFrame#tileCard:hover { border: 1px solid #38BDF8; }

QFrame#banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D3A5F, stop:1 #14233B);
    border: 1px solid #2A3A52;
    border-radius: 12px;
}

QFrame#videoRow {
    background-color: #1E293B;
    border: 1px solid #2A3A52;
    border-radius: 8px;
}
QFrame#videoRow:hover { border: 1px solid #38BDF8; }

/* ---------- 文字 ---------- */
QLabel#bannerTitle {
    font-size: 20px;
    font-weight: bold;
    color: #FFFFFF;
}
QLabel#bannerSubtitle { font-size: 12px; color: #94A3B8; }
QLabel#appTitle { font-size: 16px; font-weight: bold; color: #F1F5F9; }
QLabel#appSubtitle { color: #94A3B8; }
QLabel#cardName { font-size: 15px; font-weight: bold; color: #F1F5F9; }
QLabel#muted { color: #94A3B8; }
QLabel#groupHeader { font-size: 14px; font-weight: bold; color: #38BDF8; }
QLabel#emptyHint { color: #64748B; font-size: 14px; }

QLabel#statusPill {
    font-weight: bold;
    border-radius: 12px;
    padding: 4px 14px;
}

/* ---------- 按钮 ---------- */
QPushButton {
    background-color: #38BDF8;
    color: #06283D;
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: bold;
}
QPushButton:hover { background-color: #7DD3FC; }
QPushButton:pressed { background-color: #0EA5E9; color: #FFFFFF; }
QPushButton:disabled { background-color: #334155; color: #64748B; }

QPushButton#secondaryButton {
    background-color: #1E293B;
    color: #E5E7EB;
    border: 1px solid #334155;
}
QPushButton#secondaryButton:hover { background-color: #2A3A52; border-color: #38BDF8; }
QPushButton#secondaryButton:pressed { background-color: #334155; }

QPushButton#dangerButton {
    background-color: transparent;
    color: #F87171;
    border: 1px solid #7F1D1D;
}
QPushButton#dangerButton:hover { background-color: #3A1D24; border-color: #F87171; }
QPushButton#dangerButton:pressed { background-color: #5B2A30; }

QPushButton#smallButton {
    background-color: #1E293B;
    color: #E5E7EB;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#smallButton:hover { border-color: #38BDF8; color: #38BDF8; }
QPushButton#smallButtonDanger {
    background-color: transparent;
    color: #F87171;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#smallButtonDanger:hover { background-color: #3A1D24; }

/* ---------- 输入控件 ---------- */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background-color: #16203A;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 7px 10px;
    color: #E5E7EB;
    selection-background-color: #38BDF8;
    selection-color: #06283D;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border: 1px solid #38BDF8;
}
QLineEdit:disabled { background-color: #1E293B; color: #64748B; }
QLineEdit::placeholder { color: #64748B; }
QPlainTextEdit::placeholder { color: #64748B; }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #1E293B;
    border: 1px solid #334155;
    selection-background-color: #16203A;
    selection-color: #38BDF8;
    outline: 0;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1E293B;
    border: none;
    width: 16px;
}

/* ---------- 列表（侧边栏） ---------- */
QListWidget#sidebar {
    background-color: #16213A;
    border: 1px solid #2A3A52;
    border-radius: 10px;
    padding: 6px;
}
QListWidget#sidebar::item {
    color: #94A3B8;
    padding: 11px 14px;
    border-radius: 8px;
    margin: 1px 0;
}
QListWidget#sidebar::item:selected {
    background-color: #38BDF8;
    color: #06283D;
    font-weight: bold;
}
QListWidget#sidebar::item:hover {
    background-color: #1E293B;
    color: #E5E7EB;
}

/* ---------- 滚动区 ---------- */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ---------- 复选框 ---------- */
QCheckBox { spacing: 6px; color: #E5E7EB; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #334155;
    border-radius: 4px;
    background-color: #16203A;
}
QCheckBox::indicator:checked {
    background-color: #38BDF8;
    border: 1px solid #38BDF8;
}

/* ---------- 菜单 / 工具提示 ---------- */
QMenu {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 5px; color: #E5E7EB; }
QMenu::item:selected { background-color: #16203A; color: #38BDF8; }

QToolTip {
    background-color: #E5E7EB;
    color: #0F172A;
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #334155; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QStatusBar { background: #16213A; color: #94A3B8; }
"""


def apply_theme(app):
    app.setStyleSheet(LIGHT_BLUE_QSS)
