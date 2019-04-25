#! /usr/bin/env python
import hashlib
import os
import cv2
import json
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets, uic



class Scene(QtWidgets.QGraphicsScene):
    image_points_updated = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super(Scene, self).__init__()

    def mousePressEvent(self, ev):
        x = ev.scenePos().x()
        y = ev.scenePos().y()
        self.image_points_updated.emit((x, y))

class CamTrak(QtWidgets.QMainWindow):
    def __init__(self, cap):
        super(CamTrak, self).__init__()
        uic.loadUi('./gui/camtrak.ui',self)
        self.view_btn.clicked.connect(self.start_webcam)
        self.capture_btn.clicked.connect(self.capture_image)

        self.scene = Scene(self.gview)
        self.scene.image_points_updated.connect(self.add_known_image_points)
        self.gview.setScene(self.scene)
        self.timer = QtCore.QTimer(self, interval=5)
        self.timer.timeout.connect(self.update_frame)
        self._image_counter = 0
        self.zoom = 1

        self.capture = cap
        self.npimage = None

        self.known_image_points = []
        self.tracking_mode = False

        # Set the table headers
        self.known_geo_points_tbl.setColumnCount(3)
        self.known_geo_points_tbl.setHorizontalHeaderLabels(["Lat", "Lon", "Alt"])

        # Connect PnP button
        self.solve_pnp_btn.clicked.connect(self.solve_pnp)

        # Connect the menu actions.
        self.action_save_parameters.triggered.connect(self.on_save_parameters)
        self.action_load_parameters.triggered.connect(self.on_load_parameters)

    def on_save_parameters(self):
        obj_points = self.get_object_points()
        cam_pos    = self.get_camera_position()
        distortion = self.get_distortion_coeeficients()

        d = {
            'object positions': obj_points,
            'camera positions': cam_pos,
            'distortion coefficients': distortion
        }

        jsn = json.dumps(d)
        h = hashlib.sha1(jsn.encode('utf-8')).hexdigest()
        fn = f'{h}.json'

        with open(fn, 'w') as f:
            f.write(jsn)

        self.statusBar().showMessage(f'Parameters have been save to {fn}.')

    def on_load_parameters(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose a parameter file.", "", "JSON Files (*.json)")

        with open(path, 'r') as f:
            params = json.loads(f.read())

        print(params)
        obj_points = params['object positions']
        cam_pos = params['camera positions']
        dist_coeff = params['distortion coefficients']

        for p in obj_points:
            x, y = p['x'], p['y']
            self.add_known_image_points((x, y))

        lat = cam_pos['lat']
        self.camera_lat_line.setText(lat)

    def get_distortion_coeeficients(self):
        k1 = float(self.k1_line.text())
        k2 = float(self.k2_line.text())
        k3 = float(self.k3_line.text())
        p1 = float(self.p1_line.text())
        p2 = float(self.p2_line.text())

        d = {
            'k1': k1,
            'k2': k2,
            'k3': k3,
            'p1': p1,
            'p2': p2
        }
        return d

    def in_circle(self, point):
        x, y = point
        r = 5
        index = -1

        for i, p in enumerate(self.known_image_points):
            cx, cy = p
            dx, dy = abs(x - cx), abs(y - cy)

            if dx > r or dy > r:
                return i, False
            if dx + dy <= r:
                return i, True
            if dx**2 + dy**2 <= r**2:
                return i, True
            else:
                return i, False

        return index, False

    def add_known_image_points(self, point):
        ind, exists = self.in_circle(point)

        if exists:
            # Remove the point if it exists.
            del self.known_image_points[ind]
            self.known_geo_points_tbl.removeRow(1+ind)
            print('Removed row')
        else:
            # Or add the point.
            self.known_image_points.append(point)

            # Update the table.
            row_pos = self.known_geo_points_tbl.rowCount()
            self.known_geo_points_tbl.insertRow(row_pos)
            self.known_geo_points_tbl.setItem(row_pos, 1, QtWidgets.QTableWidgetItem(row_pos))

        # Maybe this should be the very last thing.
        self.draw_known_points()

    def draw_known_points(self):
        for p in self.known_image_points:
            x = int(p[0])
            y = int(p[1])

            cv2.circle(self.npimage, (x, y), 5, (0, 0, 255), 2, 1)

    @QtCore.pyqtSlot()
    def start_webcam(self):
        if self.capture is None:
            self.capture =cv2.VideoCapture(0)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.timer.start()

    @QtCore.pyqtSlot()
    def update_frame(self):
        ret, image = self.capture.read()

        if ret:
            self.npimage = image
            image = cv2.flip(self.npimage, 1)
            self.display_image(self.npimage, True)
        else:
            print('[ERROR] no image read from capture device')
            return

    @QtCore.pyqtSlot()
    def capture_image(self):
        flag, frame= self.capture.read()
        path = '~/data/'
        if flag:
            QtWidgets.QApplication.beep()
            name = "opencv_frame_{}.png".format(self._image_counter) 
            cv2.imwrite(os.path.join(path, name), frame)
            self._image_counter += 1

    def display_image(self, img, window=True):
        qformat = QtGui.QImage.Format_Indexed8

        if len(img.shape) == 3 :
            if img.shape[2] == 4:
                qformat = QtGui.QImage.Format_RGBA8888
            else:
                qformat = QtGui.QImage.Format_RGB888

        w, h = img.shape[:2]

        if self.known_image_points and not self.tracking_mode:
            self.draw_known_points()

        out_img = QtGui.QImage(img, h, w, img.strides[0], qformat)
        out_img = out_img.rgbSwapped()

        if window:
            self.scene.addPixmap(QtGui.QPixmap.fromImage(out_img))
            self.gview.fitInView(QtCore.QRectF(0, 0, w, h), QtCore.Qt.KeepAspectRatio)

    def get_object_points(self):
        obj_points = []

        for i in range(self.known_geo_points_tbl.rowCount()):
            lat = float(self.known_geo_points_tbl.item(i, 0).text())
            lon = float(self.known_geo_points_tbl.item(i, 1).text())
            alt = float(self.known_geo_points_tbl.item(i, 2).text())
            x, y = self.known_image_points[i]

            pos = {
                "index": i,
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "x": x,
                "y": y
            }
            obj_points.append(pos)

        return obj_points


    def get_camera_position(self):
        lat = float(self.camera_lat_line.text())
        lon = float(self.camera_lon_line.text())
        alt = float(self.camera_alt_line.text())
        cx  = float(self.cx_line.text())
        cy  = float(self.cy_line.text())
        phi = float(self.phi_line.text())
        theta = float(self.theta_line.text())
        psi = float(self.psi_line.text())

        cam_pos = {
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'cx':  cx,
            'phi': phi,
            'theta': theta,
            'psi': psi
        }
        return cam_pos
    
    def solve_pnp(self):
        # First get the 3D model points.
        obj_points = self.get_object_points()

        print(obj_points)



    def zoom_in(self):
        self.zoom *= 1.05
        self.update_view()

    def zoom_out(self):
        self.zoom /= 1.05
        self.update_view()

    def zoom_reset(self):
        self.zoom = 1
        self.update_view()

    def update_view(self):
        self.gview.setTransform(QtGui.QTransform().scale(self.zoom, self.zoom))

    def wheelEvent(self, ev):
        a = ev.angleDelta().y() / 120

        if a > 0:
            self.zoom_in()
        elif a < 0:
            self.zoom_out()

if __name__=='__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    cap = cv2.VideoCapture(0)
    window = CamTrak(cap)
    #window.setWindowTitle('main code')
    window.show()
    sys.exit(app.exec_())
