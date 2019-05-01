import cv2
from PyQt5.QtCore import pyqtSignal, QObject
from pypylon import pylon


class CVWebcam(QObject):
    # This signal is called whenever a new image is added to the queue. It is the
    # signal for the gui thread to do a pop from the queue.
    queue_updated = pyqtSignal()

    def __init__(self):
        super(CVWebcam, self).__init__()
        self.has_queue = False
        self.camera = cv2.VideoCapture(0)
        self.isopened = True

    def isOpened(self):
        return self.isopened

    def add_queue(self, queue):
        """This method must be called before the camera starts reading."""
        self.image_queue = queue
        self.has_queue = True

    def grab(self):
        while self.camera.isOpened():
            ok, img = self.camera.read()

            if ok:
                self.image_queue.append(img)
                self.queue_updated.emit()


    def close():
        self.camera.Close()