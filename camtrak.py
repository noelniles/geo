#! /usr/bin/env python
import argparse
import hashlib
import os
import cv2
from datetime import datetime
import json
from functools import partial
from queue import Queue

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from astropy.io import fits

from geometry import geodetic_to_ecef
from gui import ClickableScene
from cameras import Basler
from trackers import SingleTracker
from geometry import inside_circle


class CamTrak(QtWidgets.QMainWindow):

    def __init__(self, cap):
        super(CamTrak, self).__init__()
        uic.loadUi('./gui/camtrak.ui',self)
        self.setWindowIcon(QtGui.QIcon('./assets/icons/radar_icon.png'))

        self.image_queue = Queue()
        self.scene = ClickableScene(self.gview)
        self.gview.setScene(self.scene)
        self.mask_scene = ClickableScene(self.mask_view)
        self.mask_view.setScene(self.mask_scene)
        self.altered_image = None
        self.original_image = None
        self.connect_signals()
        #self.timer = QtCore.QTimer(self, interval=0.1)
        #self.timer.timeout.connect(self.update_frame)
        self._image_counter = 0
        self.zoom = 1

        self.known_image_points = []
        self.tracking_mode = False

        # Set the table headers
        self.known_geo_points_tbl.setColumnCount(3)
        self.known_geo_points_tbl.setHorizontalHeaderLabels(["Lat", "Lon", "Alt"])

        self.param_file = None

        # Different modes.
        self.tracking = False
        self.tracker = SingleTracker()
        self.current_tracked_point = None

        # Image save stuff.
        self.image_save_type = 'bmp'
        self.image_type_box.currentIndexChanged.connect(self.on_image_type_selection_changed)
        self.metadata_filename = None
        self.save_directory = None
        self.starting_time = datetime.utcnow().isoformat().replace(':', "_")

        # OS stuff
        self.home = os.path.expanduser('~')

        # Set up the camera stuff.
        self.camera = cap
        self.camera_thread = QtCore.QThread()
        self.camera.moveToThread(self.camera_thread)
        self.camera.queue_updated.connect(self.update_frame)
        self.camera_thread.start()

        # Finally, load the last session if there is one.
        self.load_previous_session()

    def on_image_type_selection_changed(self, index):
        self.image_save_type = self.image_type_box.itemText(index).lower()
        print(f'Saving {self.image_save_type} images')

    def on_tracking_mode(self):
        self.tracking = not self.tracking
        msg = 'Tracking Mode' if self.tracking else ''
        self.statusBar().showMessage(msg)

    def connect_signals(self):
        self.view_btn.clicked.connect(self.start_webcam)
        self.capture_btn.clicked.connect(self.capture_image)
        self.scene.image_points_updated.connect(self.add_known_image_points)
        self.solve_pnp_btn.clicked.connect(self.solve_pnp)
        self.action_save_parameters.triggered.connect(self.on_save_parameters)
        self.action_load_parameters.triggered.connect(self.on_load_parameters)
        self.action_track.triggered.connect(self.on_tracking_mode)
        self.action_open_image.triggered.connect(self.on_open_image)

    def load_previous_session(self):
        path = './previous_session.json'

        if os.path.exists(path):
            with open(path) as f:
                prev_session = json.load(f)

            prev_session_param_file = prev_session['param file']

            self.on_load_parameters(prev_session_param_file)

    def on_open_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Choose an image.", self.home, "Images (*.bmp *BMP *.jpg *.JPG *.png *.PNG *.tif *.tiff *.TIF *.TIFF *.fts *.FTS *.fits *.FITS)")

        self.original_image = cv2.imread(path)
        self.altered_image = self.original_image.copy()
        self.display_image()

    def on_save_parameters(self):
        """Callback function that is called when the Save Parameters btn 
        is clicked.
        """
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
        """Callback function that is called when the "Load Parameters" button
        is called.
        """
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

    def add_tracking_point(self, point):
        self.current_tracked_point = point

    def add_pnp_point(self, point, latlonalt):
        """This function is called whenever the scene is double clicked 
        in tracking mode.

        Arguments:
            point (2-tuple): (x, y) of clicked point
            latlonalt (3-tuple): the user entered (lat, lon, alt)

        Returns:
            None
        """
        ind, exists = inside_circle(point, self.known_image_points)
            
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

    def add_known_image_points(self, point, latlonalt=None):
        """Callback function that is called when the scene is clicked. First,
        we add the point to either the tracking list or the PNP list and then
        we call draw_known_points at the very end in order to draw the points
        on the image.

        Arguments:
            point (2-tuple): (x, y) of clicked point

        Returns:
            None
        """
        if self.tracking:
            self.add_tracking_point(point)
        else:
            self.add_pnp_point(point, latlonalt)

        # Finally, draw the points.
        self.draw_known_points()

    def draw_known_points(self):
        """This function draws points onto the visible image. All of the 
        drawing happens on a copy of the image so the original is maintained.
        """
        if self.tracking:
            if self.current_tracked_point == None:
                return
            p = self.current_tracked_point
            x, y = (int(u) for u in p)
            cv2.circle(self.altered_image, (x, y), 10, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.putText(self.altered_image, f'az:{x:.3f} alt:{y:.3f}', (x, y), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255))
            self.statusBar().showMessage(f'az: {x:.3f} alt: {y:.3f}')
        else:
            for p in self.known_image_points:
                x, y = (int(u) for u in p)

                cv2.circle(self.altered_image, (x, y), 5, (0, 0, 255), 1, cv2.LINE_AA)
                cv2.putText(self.altered_image, f'x:{x} y:{y}', (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255))

    def update_frame_tracking(self):
        """This function is called when we need to update the scene in tracking
        mode. If we don't have any points to track we just return, because there
        is nothing to do. If the tracker isn't initialized then we initialize it
        If the tracker is initialized we update it and then draw the box on the.
        scene.
        """
        if not self.current_tracked_point:
            return

        if not self.tracker.initialized:
            x, y = self.current_tracked_point
            roi = (x, y, 50, 50)
            self.tracker.initialize(self.original_image, roi)
            return

        self.roi = self.tracker.update(self.original_image)
        x, y, w, h = self.roi

        cv2.circle(self.altered_image, (int(x), int(y)), 10, (0, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(self.altered_image, f'az:{x:.3f}alt:{y:.3f}', (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255))

    @QtCore.pyqtSlot()
    def start_webcam(self):
        """This slot is called when the user clicks the "view" button. It's main
        purpose is to create the camera device.
        """
        self.timer.start()
        if self.camera is None:
            self.camera = cv2.VideoCapture(0)
        self.timer.start()

    @QtCore.pyqtSlot()
    def update_frame(self):
        """This is the slot that actaully reads an image from the camera."""
        #ret, image = self.camera.read()
        image = self.image_queue.pop()
        self.original_image = image
        self.altered_image = image.copy()

        if self.tracking:
            self.update_frame_tracking()
            self.display_image(True)
        else:
            image = cv2.flip(self.altered_image, 1)
            self.display_image(True)

    @QtCore.pyqtSlot()
    def capture_image(self):
        """This is the slot that saves an image to a file."""
        ext = self.image_save_type.lower()

        if ext == 'fits':
            self.save_fits()
            self._image_counter += 1
        else:
            img = self.original_image
            path = os.path.join(self.home, 'data')
            name = "camtrak_frame_{}.png".format(self._image_counter) 
            fn = os.path.join(path, name)
            cv2.imwrite(fn, img)

            QtWidgets.QApplication.beep()
            self.statusBar().showMessage(f'Saved image to {fn}')
            self._image_counter += 1

    def user_create_fits_header(self):
        pass

    def save_fits(self):
        hdu = fits.PrimaryHDU()

        hdu.data = self.original_image[::]
        hdr = hdu.header

        if not self.metadata_filename:
            # Let the user choose a JSON file containing fits header.
            self.metadata_filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose a FITS header file.", "", "JSON Files (*.json)")
            self.user_create_fits_header()
            
        if self.metadata_filename:
            # A metadata file exists so load it into a dict that will become the header.
            with open(self.metadata_filename, 'r') as f:
                d = json.load(f)

        if not self.save_directory:
            self.save_directory, _ = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a directory")


        directory = os.path.join(self.save_directory, self.starting_time)
        if not os.path.exists(directory):
            os.makedirs(directory)

        path = os.path.join(directory, f'{self.image_counter}.fits')
        hdu.writeto(path)

    def display_image(self, window=True):
        qformat = QtGui.QImage.Format_Indexed8
        img = self.altered_image

        if len(img.shape) == 3 :
            if img.shape[2] == 4:
                qformat = QtGui.QImage.Format_RGBA8888
            else:
                qformat = QtGui.QImage.Format_RGB888

        w, h = img.shape[:2]

        self.draw_known_points()

        out_img = QtGui.QImage(img, h, w, img.strides[0], qformat)
        out_img = out_img.rgbSwapped()

        if window:
            self.gview.setTransform(QtGui.QTransform().scale(self.zoom, self.zoom))
            self.scene.addPixmap(QtGui.QPixmap.fromImage(out_img))

            if self.tracking:
                # This is to show the image mask after the preparation that is
                # done inside the tracker. But the tracker might not have an 
                # image yet so we need to wait until it does. 
                if not self.current_tracked_point:
                    return
                mask = self.tracker.prepped_image
                qmask = QtGui.QImage(mask, h, w, mask.strides[0], qformat)
                qmask = qmask.rgbSwapped()
                self.mask_view.setTransform(QtGui.QTransform().scale(self.zoom, self.zoom))
                self.mask_scene.addPixmap(QtGui.QPixmap.fromImage(qmask))

    def get_object_points(self):
        obj_points = []

        print('row count: ', self.known_geo_points_tbl.rowCount())
        for i in range(1, self.known_geo_points_tbl.rowCount()):
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
        h, w = self.original_image.shape[:2]
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

def cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('-camera', choices=['webcam', 'basler', 'flir'], default='webcam')

    return ap.parse_args()

if __name__=='__main__':
    import sys
    args = cli()
    app = QtWidgets.QApplication(sys.argv)
    if args.camera == 'basler':
        cap = Basler()
    else:
        cap = cv2.VideoCapture(0)

    window = CamTrak(cap)
    window.show()
    sys.exit(app.exec_())
