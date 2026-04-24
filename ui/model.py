import logging
import numpy as np
from PyQt5 import QtGui, QtCore, QtWidgets 
from PyQt5.QtCore import QObject
import pyqtgraph as pg
from radar.radar_helper import Radar, RadarResults, RadarTransmissionError


class RadarWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    newRangeProfile = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    newRDM = QtCore.pyqtSignal(np.ndarray)
    newTargets = QtCore.pyqtSignal(list)
    
    def run(self):
        self.please_stop = False

        radar = Radar(
            com_ctrl='/dev/ttyACM0',  # XDS110 Class Application/User UART
            com_data='/dev/ttyACM1',  # XDS110 Class Auxiliary Data Port
            waveform_config='radar/profile_range_doppler.cfg'
        )
        print('Radar module initialized.')

        while not self.please_stop:
            # read new radar data from serial port
            results = radar.read() # FIXME: if Radar is blocked, thread can not terminate cleanly

            if hasattr(results, 'rangedata') and hasattr(results, 'noisedata'):
                if (not self.please_stop):
                    self.newRangeProfile.emit(results.rangedata, results.noisedata)

            if hasattr(results, 'range_doppler_heatmap'):
                if (not self.please_stop):
                    self.newRDM.emit(results.range_doppler_heatmap)

            if hasattr(results, 'targets'):
                if (not self.please_stop):
                    self.newTargets.emit(results.targets)

        if not self.please_stop:
            self.finished.emit()

    def stop(self):
        self.please_stop = True


class PointCloudPersistent:
    _points = []
    max_age = 100

    def __init__(self):
        pass

    def addPoint(self, target:dict):
        if target['dg'] == 0:
            return
        pt = {
            'pos': (target['x'], target['y']),
            'size': 10*np.log10(target['peakval']),
            'symbol': 'h',
            #'pen': {'color': 'b', 'width': 1}, 
            'pen': None, # no border on spots
            'age': 0,
            'dg': target['dg'],
        }
        self._points.append(pt)

    def getSpots(self) -> list[dict]:
        """generate "spot" dics for use with pyqtgraph scatter plot"""
        spots = []
        for pt in self._points:
            spot = {}
            for itm in ['pos', 'size', 'symbol', 'pen']:
                spot[itm] = pt[itm]
            alpha = 255 - 2*pt['age']
            r = b = 100
            dg = pt['dg']
            if dg > 0:
                r = min(r+10*dg, 255)
            else:
                b = max(b-10*dg, 0)
            spot['brush'] = pg.mkBrush(r, 100, b, alpha)
            spots.append(spot)
        return spots

    def update(self):
        # some time has passed, fade out the points
        for pt in self._points:
            pt['age'] += 1
            if pt['age'] > self.max_age:
                del pt

class SpeedHistory:
    def __init__(self, n_frames=100):
        self._speeds = [0] * n_frames
        self._t = np.arange(n_frames)

    def addSpeed(self, v):
        self._speeds = self._speeds[1:]
        self._speeds.append(v)

    def getSpeeds(self):
        return self._t, self._speeds

# collect radar data
# do any non-visual processing
# send data to UI whever it changes
class Controller(QObject):

    aboutToQuit = QtCore.pyqtSignal()
    newPointCloud = QtCore.pyqtSignal(list)
    newTargets = QtCore.pyqtSignal(list)
    newRDM = QtCore.pyqtSignal(np.ndarray)
    newRangeProfile = QtCore.pyqtSignal(np.ndarray)
    newSpeeds = QtCore.pyqtSignal(np.ndarray, np.ndarray)
    newRadarFrame = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.speeds = SpeedHistory(100)
        self.pointcloud = PointCloudPersistent()

        self.thread = QtCore.QThread()
        self.worker = RadarWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.worker.newRDM.connect(self.handleRDM)
        self.worker.newTargets.connect(self.handleTargets)

        self.aboutToQuit.connect(self.worker.stop)
        self.thread.start()

    def handleRadarFrame(self):
        self.newRadarFrame.emit()
        
        # update persistent point cloud
        self.pointcloud.update()
        spots = self.pointcloud.getSpots()
        self.newPointCloud.emit(spots)
        
    def handleRDM(self, rdm:np.ndarray):
        self.handleRadarFrame()
        self.newRDM.emit(rdm)
        self.newRangeProfile.emit(rdm[:, 0]) # DG0

    def handleTargets(self, targets:list[dict]):
        # update persistent target map
        for tgt in targets:
            self.pointcloud.addPoint(tgt)
        
        # update speed vs. time 
        rg = [t.get('rg') for t in targets]
        dg = [t.get('dg') for t in targets]
        max_dg = np.max(np.abs(dg))
        self.speeds.addSpeed(max_dg) # FIXME: convert to m/s
        t, v = self.speeds.getSpeeds()
        self.newSpeeds.emit(np.array(t), np.array(v))
        
        # pass on to plot widgets
        self.newTargets.emit(targets)