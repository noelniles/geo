#! /usr/bin/env python
import hashlib
import os
import cv2
import json
from functools import partial

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from geometry import geodetic_to_ecef


class Scene(QtWidgets.QGraphicsScene):
    image_points_updated = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super(Scene, self).__init__()

    def mouseDoubleClickEvent(self, ev):
        x = ev.scenePos().x()
        y = ev.scenePos().y()
        self.image_points_updated.emit((x, y))


class CamTrak(QtWidgets.QMainWindow):

    def __init__(self, cap):
        super(CamTrak, self).__init__()
        uic.loadUi('./gui/camtrak.ui',self)

        self.camera = cap
        self.scene = Scene(self.gview)
        self.gview.setScene(self.scene)
        self.npimage = None
        self.connect_signals()
        self.timer = QtCore.QTimer(self, interval=0.1)
        self.timer.timeout.connect(self.update_frame)
        self._image_counter = 0
        self.zoom = 1

        self.known_image_points = []
        self.tracking_mode = False

        # Set the table headers
        self.known_geo_points_tbl.setColumnCount(3)
        self.known_geo_points_tbl.setHorizontalHeaderLabels(["Lat", "Lon", "Alt"])

        self.param_file = None

        # Load the last session.
        self.load_previous_session()

        # Different modes.
        self.tracking = False

    def on_tracking_mode(self):
        self.tracking = not self.tracking
        print('TRACKINNNNNN', self.tracking)

    def connect_signals(self):
        self.view_btn.clicked.connect(self.start_webcam)
        self.capture_btn.clicked.connect(self.capture_image)
        self.scene.image_points_updated.connect(self.add_known_image_points)
        self.solve_pnp_btn.clicked.connect(self.solve_pnp)
        self.action_save_parameters.triggered.connect(self.on_save_parameters)
        self.action_load_parameters.triggered.connect(self.on_load_parameters)
        self.action_track.triggered.connect(self.on_tracking_mode)

    def load_previous_session(self):
        path = './previous_session.json'

        if os.path.exists(path):
            with open(path) as f:
                prev_session = json.load(f)

            prev_session_param_file = prev_session['param file']

            self.on_load_parameters(prev_session_param_file)

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
        self.param_file = fn

    def on_load_parameters(self, filename=None):
        if filename is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose a parameter file.", "", "JSON Files (*.json)")
        else:
            path = filename

        if path == '' or path is None:
            return

        self.param_file = path

        with open(self.param_file, 'r') as f:
            params = json.loads(f.read())

        obj_points = params['object positions']
        cam_pos    = params['camera positions']
        dist_coeff = params['distortion coefficients']

        for p in obj_points:
            x, y = p['x'], p['y']
            lat, lon, alt = p['lat'], p['lon'], p['alt']
            self.add_known_image_points((x, y), latlonalt=(lat, lon, alt))

        self.camera_lat_line.setValue(float(cam_pos['lat']))
        self.camera_lon_line.setValue(float(cam_pos['lon']))
        self.camera_alt_line.setValue(float(cam_pos['alt']))
        self.cx_line.setValue(float(cam_pos['cx']))
        self.cy_line.setValue(float(cam_pos['cy']))
        self.phi_line.setValue(float(cam_pos['phi']))
        self.theta_line.setValue(float(cam_pos['theta']))
        self.psi_line.setValue(float(cam_pos['psi']))

        self.k1_line.setValue(float(dist_coeff['k1']))
        self.k2_line.setValue(float(dist_coeff['k2']))
        self.k3_line.setValue(float(dist_coeff['k3']))
        self.p1_line.setValue(float(dist_coeff['p1']))
        self.p2_line.setValue(float(dist_coeff['p2']))

        self.statusBar().showMessage(f'Loaded parameters from {self.param_file}')

    def inside_circle(self, point):
        """This is at least correct and for small list of points not too slow."""
        index = -1

        for i, p in enumerate(self.known_image_points):
            x, y = point
            a, b = p
            r = 5

            if (x - a)*(x - a) + (y - b)*(y - b) < r*r:
                return i, True
            
        return index, False


    def in_circle(self, point):
        """There's some kind of bud in here."""
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

    def add_known_image_points(self, point, latlonalt=None):
        ind, exists = self.inside_circle(point)

        if exists:
            # Remove the point if it exists.
            del self.known_image_points[ind]
            self.known_geo_points_tbl.removeRow(ind)
        else:
            # Or add the point.
            self.known_image_points.append(point)

            # Update the table.
            row_pos = self.known_geo_points_tbl.rowCount()
            self.known_geo_points_tbl.insertRow(row_pos)

            if latlonalt:
                self.known_geo_points_tbl.setItem(
                    row_pos, 0, QtWidgets.QTableWidgetItem(str(latlonalt[0])))
                self.known_geo_points_tbl.setItem(
                    row_pos, 1, QtWidgets.QTableWidgetItem(str(latlonalt[1])))
                self.known_geo_points_tbl.setItem(
                    row_pos, 2, QtWidgets.QTableWidgetItem(str(latlonalt[2])))

        # Maybe this should be the very last thing.
        self.draw_known_points()

    def draw_known_points(self):
        for p in self.known_image_points:
            x = int(p[0])
            y = int(p[1])

            cv2.circle(self.npimage, (x, y), 5, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.putText(self.npimage, f'x:{x} y:{y}', (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1/8, (0, 0, 255))

    @QtCore.pyqtSlot()
    def start_webcam(self):
        self.timer.start()
        if self.camera is None:
            self.capture = cv2.VideoCapture(0)
        self.timer.start()

    @QtCore.pyqtSlot()
    def update_frame(self):
        ret, image = self.camera.read()
        print(image.shape)
        self.npimage = image
        image = cv2.flip(self.npimage, 1)
        self.display_image(True)

    @QtCore.pyqtSlot()
    def capture_image(self):
        flag, frame= self.capture.read()
        path = '~/data/'
        if flag:
            QtWidgets.QApplication.beep()
            name = "opencv_frame_{}.png".format(self._image_counter) 
            cv2.imwrite(os.path.join(path, name), frame)
            self._image_counter += 1

    def display_image(self, window=True):
        qformat = QtGui.QImage.Format_Indexed8
        img = self.npimage

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
            self.gview.setTransform(QtGui.QTransform().scale(self.zoom, self.zoom))
            self.scene.addPixmap(QtGui.QPixmap.fromImage(out_img))

    def get_object_points(self):
        obj_points = []

        print('row count: ', self.known_geo_points_tbl.rowCount())
        for i in range(self.known_geo_points_tbl.rowCount()):
            print('on row ', i)
            lat = float(self.known_geo_points_tbl.item(i, 0).text())
            lon = float(self.known_geo_points_tbl.item(i, 1).text())
            print('**', lat, lon)
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

        print('camera ecef position ', geodetic_to_ecef(lon, lat, alt))

        cam_pos = {
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'cx':  cx,
            'cy': cy,
            'phi': phi,
            'theta': theta,
            'psi': psi
        }
        return cam_pos

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
    
    def solve_pnp(self):
        # FAKE camera matrix
        h, w = self.npimage.shape[:2]
        focal_length = 1
        cx, cy = (w//2, h//2)
        dist_coeffs = np.zeros((4,1))
        cam_mat = np.array(
            [
                [focal_length, 0, cx],
                [0, focal_length, cy],
                [0, 0, 1]
            ],
            dtype="double"

        )
        dist_coeffs = np.zeros((4,1))

        # First get the 3D model points.
        llas = []
        obj_points = self.get_object_points()

        for p in obj_points:
            llas.append(np.array([p['lat'], p['lon'], p['alt']]))
        
        # Now get the 2d image points.
        img_points = self.known_image_points
        print(obj_points)
        print(img_points)

        sol = cv2.solvePnP(np.array(llas), np.asarray(img_points, 'float32'), cam_mat, dist_coeffs)

        print(sol)

    def zoom_in(self):
        self.zoom *= 1.05
        self.display_image()

    def zoom_out(self):
        self.zoom /= 1.05
        self.display_image()

    def zoom_reset(self):
        self.zoom = 1
        self.display_image()

    def update_view(self):
        self.gview.setTransform(QtGui.QTransform().scale(self.zoom, self.zoom))

    def wheelEvent(self, ev):
        a = ev.angleDelta().y() / 120

        if a > 0:
            self.zoom_in()
        elif a < 0:
            self.zoom_out()

    def closeEvent(self, ev):
        session = {}
        if self.param_file:
            session.update({'param file': self.param_file})

        with open('previous_session.json', 'w') as f:
            json.dump(session, f)

        print('Saved session to previous_session.json')

if __name__=='__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    cap = cv2.VideoCapture(0)
    window = CamTrak(cap)
    window.show()
    sys.exit(app.exec_())
