import cv2


class SingleTracker:
    def __init__(self):
        self.t = cv2.TrackerCSRT_create()
        self.roi = (0, 0, 0, 0)
        self.initialized = False
        self.fgbg = cv2.createBackgroundSubtractorMOG2() 

        self.prepped_image = None

    def prep(self, img):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.erode(thresh, None, iterations=2)
        thresh = cv2.dilate(thresh, None, iterations=4)

        fgmask = self.fgbg.apply(img, 0.9)
        fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel, iterations=2)

        self.prepped_image = cv2.cvtColor(fgmask, cv2.COLOR_GRAY2RGB)
        return blur

    def initialize(self, image, roi):
        image = self.prep(image)
        ok = self.t.init(image, roi)

        if not ok:
            print('problem intializing tracker')

        self.initialized = True

    def update(self, image):
        image = self.prep(image)
        ok, self.roi = self.t.update(image)

        if not ok:
            print('no luck tracking')
        return self.roi