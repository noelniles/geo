from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsScene

class ClickableScene(QGraphicsScene):
    image_points_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super(ClickableScene, self).__init__()
        self.painter = QPainter()
        #self.painter.begin(self)
        self.painter.setBrush(Qt.white)
        self.painter.setRenderHint(QPainter.Antialiasing)
        self.painter.setPen(Qt.red)

        self.mode = 'pnp'
        self.objs = []

    def mouseDoubleClickEvent(self, ev):
        x = ev.scenePos().x()
        y = ev.scenePos().y()
        self.objs.append((x, y))
        self.image_points_updated.emit((x, y))

    def paintEvent(self, ev):
        for box in self.objs:
            x, y, w, h = box
            center = QPoint(x, y)
            self.painter.drawEllipse(center, 10, 10)

