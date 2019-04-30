from random import randint

import cv2


class MultiTracker:
    def __init__(self):
        self.objs = []
        self.algs = []
        self.colors = []
        self.trackers = cv2.MultiTracker_create()
        self.istracking = False

    def init(self, frame, objs):
        """Add the first set of objects.
        
        Arguments:
            frame (ndarray): the image to initialize the tracker with
            objs (list): the object to add to the tracker [(x, y, w, h), ...]
        """
    
        # First, add the objects to the list of objects.
        self.objs.extend(objs)

        for obj in self.objs:
            self.algs.append(cv2.createTrackerByName('csrt'))
            color = (randint(0, 255), randint(0, 255), randint(0, 255))
            self.colors.append(color)

        self.trackers.add(self.algs, frame, self.objs)
        self.istracking = True

    def add_object(self, frame, obj):
        self.objs.extend(obj)

    def remove_obj(self, obj):
        pass

    def update(self, frame):
        ok, boxes = self.trackers.update(frame)
        return ok