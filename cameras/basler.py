from PyQt5.QtCore import pyqtSignal, QObject
from pypylon import pylon


class Basler(QObject):
    # This signal is called whenever a new image is added to the queue. It is the
    # signal for the gui thread to do a pop from the queue.
    queue_updated = pyqtSignal()

    def __init__(self):
        super(Basler, self).__init__()
        self.has_queue = False
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()
        self.isopened = True
        self.camera.PixelFormat  = "Mono12"
        self.camera.GainAuto     = "Continuous"
        self.camera.ExposureAuto = "Continuous"
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly) 

    def isOpened(self):
        return self.isopened

    def add_queue(self, queue):
        """This method must be called before the camera starts reading."""
        self.image_queue = queue
        self.has_queue = True

    def grab(self):
        while self.camera.IsGrabbing():
            grabResult = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grabResult.GrabSucceeded():
                # Access the image data
                image = self.converter.Convert(grabResult)
                npimage = image.GetArray()
                
                if not self.image_queue.full():
                    self.image_queue.put(npimage)
                    self.queue_updated.emit()

                #return True, npimage

        #return False, None

    def close():
        camera.StopGrabbing()