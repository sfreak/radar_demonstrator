import logging
import numpy as np
from PyQt5 import QtGui, QtCore, QtWidgets 
import pyqtgraph as pg
from ti_rdm.radar_helper import Radar, RadarResults, RadarTransmissionError

# import the "form class" from your compiled UI
from template import Ui_CustomWidget

g_mode = 'RDM'

logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w')
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

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
            #waveform_config='ti_rdm/profile_range.cfg'
            waveform_config='ti_rdm/profile_range_doppler.cfg'
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
            #'size': target['peakval'],
            #'size': 5,
            'size': 10*np.log10(target['peakval']),
            'symbol': 'h',
            #'pen': {'color': 'b', 'width': 1}, 
            'pen': None,
            'age': 0,
            'dg': target['dg'],
        }
        self._points.append(pt)

    def getSpots(self) -> list[dict]:
        spots = []
        for pt in self._points:
            spot = pt.copy()
            del spot['age']
            del spot['dg']
            #spot['brush'] = pg.intColor()
            alpha = 255 - 2*pt['age']
            if alpha < 0:
                continue
            r = b = 100
            dg = pt['dg']
            if dg > 0:
                r = min(r+10*dg, 255)
            else:
                b = max(b-10*dg, 0)
            spot['brush'] = pg.mkBrush(r, 100, b, alpha)
            spots.append(spot)
        return spots

    #def getBrushes(self):

    #    brushes_table = [QtGui.QBrush(QtGui.QColor(*color)) for color in colors]

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


class CustomWidget(QtWidgets.QWidget):
    aboutToQuit = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(CustomWidget, self).__init__(parent=parent)

        pg.setConfigOption('background', (255,255,255, 0))

        # set up the form class as a `ui` attribute
        self.ui = Ui_CustomWidget()
        self.ui.setupUi(self)

        self.speeds = SpeedHistory(100)

        # Range profile plot
        self.trace0 = self.ui.plotWidget.plot(
            x=[0.0, 1.0, 2.0, 3.0],
            y=[4.4, 2.5, 2.1, 2.2],
            pen=pg.mkPen('black', width=3),
            symbol='o')
        self.trace1 = self.ui.plotWidget.plot(
            x=[0.0, 1.0, 2.0, 3.0],
            y=[4.4, 2.5, 2.1, 2.2],
            pen=pg.mkPen('green', width=3),
            symbol='o')
        self.ui.plotWidget.setYRange(30, 110)
        self.ui.plotWidget.setLabel('left', 'Received Power')
        self.ui.plotWidget.setLabel('bottom', 'Doppler Gate')
        
        # range-Doppler heatmap plot
        self.img = pg.ImageItem(
            image=np.zeros((128, 64)),
            levels=(40,100)
        )
        
        tr = QtGui.QTransform()
        tr.translate(0, -32) # move DG32 to 0
        self.img.setTransform(tr) # assign transform

        self.ui.imageWidget.setRange(yRange=(-32, 32), xRange=(0,127), padding=0)
        self.ui.imageWidget.addItem(self.img)
        self.img.setColorMap(pg.colormap.get('viridis'))
        self.ui.imageWidget.setLabel('bottom', 'Range Gate')
        self.ui.imageWidget.setLabel('left', 'Doppler Gate')
        # target list overlay on RDM
        self.sc = pg.ScatterPlotItem(x=[], y=[])
        self.ui.imageWidget.addItem(self.sc)

        # persistent point cloud
        self.pointcloud = PointCloudPersistent()
        self.sc_points = pg.ScatterPlotItem(x=[], y=[])
        self.ui.pointWidget.setAspectLocked()
        self.ui.pointWidget.setYRange(0, 4, padding=0) # botesight
        self.ui.pointWidget.setXRange(-2, 2, padding=0) # left/right
        #self.ui.pointWidget.setLimits(xMin=0, xMax=2, yMin=-2, yMax=2)
        self.ui.pointWidget.addItem(self.sc_points)
        self.ui.pointWidget.setLabel('bottom', 'X Position / m')
        self.ui.pointWidget.setLabel('left', 'Y Position / m')

        # speed history
        self.speed_trace = self.ui.speedWidget.plot(
            x=[], y=[],
            pen=pg.mkPen('black', width=3),
            symbol='o')
        self.ui.speedWidget.setYRange(0, 31)
        self.ui.speedWidget.setLabel('bottom', 'Time')
        self.ui.speedWidget.setLabel('left', '|Speed|')
        # highscore
        self.speed_template = '<span style="color: red; font-size: 16pt;">Highest speed: {}</span>'
        self.speed_text = pg.TextItem(html=self.speed_template.format(0))
        self.ui.speedWidget.addItem(self.speed_text)
        self.speed_text.setPos(30,20)


        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

        self.thread = QtCore.QThread()
        self.worker = RadarWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.worker.newRDM.connect(self.newRDM)
        self.worker.newRangeProfile.connect(self.newRangeProfile)
        self.worker.newTargets.connect(self.newTargets)

        self.aboutToQuit.connect(self.worker.stop)
        self.thread.start()

    def newRadarFrame(self):
        # update persistent point cloud
        self.pointcloud.update()
        spots = self.pointcloud.getSpots()
        logging.info('%d spots', len(spots))
        self.sc_points.setData(spots=spots)

    def newRangeProfile(self, pr:np.ndarray, pn:np.ndarray):
        #print('got radar data: ', pr)
        # ramge profile is just Doppler zero - moving targets will not show up
        # if RDM is availabe, better use np.max(rdm, axis=1)
        #self.trace.setData(pr)
        pass

    def newRDM(self, rdm:np.ndarray):
        #print('got RDM')
        imdata = np.fft.fftshift(rdm, axes=1)
        self.img.setImage(imdata)

        #self.trace0.setData(np.max(rdm, axis=1))
        self.trace0.setData(rdm[:, 0]) # stationary
        #self.trace1.setData(np.max(rdm[3:58], axis=1)) # moving - does not work well as the doppler window smears targets

        # TODO: add background subtraction
        self.newRadarFrame()

    def newTargets(self, targets:list[dict]):
        rg = [t.get('rg') for t in targets]
        dg = [t.get('dg') for t in targets]
        
        max_dg = np.max(np.abs(dg))
        # TODO: could do velocity interpolation based on RDM to get smoother trace
        self.speeds.addSpeed(max_dg) # FIXME: convert to m/s
        t, v = self.speeds.getSpeeds()
        self.speed_trace.setData(x=t, y=v)
        self.speed_text.setHtml(self.speed_template.format(np.max(v)))

        # target overlay on RDM
        self.sc.setData(x=rg, y=dg)

        # persistent target map
        for tgt in targets:
            self.pointcloud.addPoint(tgt)


if __name__ == '__main__':

    app = QtWidgets.QApplication([])
    widget = CustomWidget()
    app.aboutToQuit.connect(widget.aboutToQuit)
    widget.show()
    app.exec_()
