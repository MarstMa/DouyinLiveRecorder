"""一次性脚本：生成 exe 图标 icon.ico（蓝色圆标 + 「录」字）。"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter


def build(size: int = 256) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64.0
    p.setBrush(QColor("#38BDF8"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(int(4 * s), int(4 * s), int(56 * s), int(56 * s))
    p.setPen(QColor("#06283D"))
    f = QFont("Microsoft YaHei")
    f.setBold(True)
    f.setPixelSize(int(30 * s))
    p.setFont(f)
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, "录")
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication([])
    img = build(256)
    ok = img.save("icon.ico", "ICO")
    print("saved icon.ico:", ok)
