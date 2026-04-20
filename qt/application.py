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
            com_ctrl='COM10',  # XDS110 Class Application/User UART
            com_data='COM9',  # XDS110 Class Auxiliary Data Port
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


class CustomWidget(QtWidgets.QWidget):
    aboutToQuit = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super(CustomWidget, self).__init__(parent=parent)

        pg.setConfigOption('background', (255,255,255, 0))

        # set up the form class as a `ui` attribute
        self.ui = Ui_CustomWidget()
        self.ui.setupUi(self)

        # access your UI elements through the `ui` attribute
        #self.ui.plotWidget.setBackground('white')

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

        self.sc = pg.ScatterPlotItem(x=[], y=[])
        self.ui.imageWidget.addItem(self.sc)


        # simple demonstration of pure Qt widgets interacting with pyqtgraph
        self.ui.checkBox.stateChanged.connect(self.toggleMouse)

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

    def newTargets(self, targets:list[dict]):
        #x = [t.get('x') for t in targets]
        #y = [t.get('y') for t in targets]
        x = [t.get('rg') for t in targets]
        y = [t.get('dg') for t in targets]
        self.sc.setData(x=x, y=y)
        # TODO: add persistence
        # TODO: move to separate plot

    def toggleMouse(self, state):
        if state == QtCore.Qt.Checked:
            enabled = True
        else:
            enabled = False

        self.ui.plotWidget.setMouseEnabled(x=enabled, y=enabled)


if __name__ == '__main__':

    app = QtWidgets.QApplication([])
    widget = CustomWidget()
    app.aboutToQuit.connect(widget.aboutToQuit)
    widget.show()
    app.exec_()
