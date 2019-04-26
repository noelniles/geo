from pypylon import pylon


class Basler:
    def __init__(self):
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

    def read(self):
        if self.camera.IsGrabbing():
            grabResult = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grabResult.GrabSucceeded():
                # Access the image data
                image = self.converter.Convert(grabResult)
                npimage = image.GetArray()
                
                return True, npimage

        return False, None

    def close():
        camera.StopGrabbing()