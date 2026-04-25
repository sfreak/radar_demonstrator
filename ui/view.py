import logging
import numpy as np
from PyQt5 import QtGui, QtCore, QtWidgets 
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from radar.parse_config import Waveform



# make all plots transparent
pg.setConfigOption('background', (255,255,255, 0))
pg.setConfigOption('foreground', 'k')

class PlotRDM(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        # range-Doppler heatmap plot
        self.img = pg.ImageItem(
            image=np.zeros((waveform.n_rg, waveform.n_dg)),
            levels=(40,100) # FIXME
        )
        
        tr = QtGui.QTransform()
        tr.translate(0, -waveform.n_dg//2) # move DG32 to 0
        self.img.setTransform(tr) # assign transform
        self.img.setColorMap(pg.colormap.get('viridis'))

        self.setRange(yRange=(-waveform.n_dg//2, waveform.n_dg//2-1), xRange=(0, waveform.n_rg), padding=0)
        self.addItem(self.img)

        self.setLabel('bottom', 'Range Gate')
        self.setLabel('left', 'Doppler Gate')

        # target list overlay on RDM
        self.sc = pg.ScatterPlotItem(x=[], y=[])
        self.addItem(self.sc)

    def newTargets(self, targets:list[dict]):
        rg = [t.get('rg')+0.5 for t in targets]
        dg = [t.get('dg')+0.5 for t in targets]
        self.sc.setData(x=rg, y=dg)

    def newRDM(self, rdm:np.ndarray):
        imdata = np.fft.fftshift(rdm, axes=1)
        self.img.setImage(imdata)


class PlotRangeProfile(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        # Range profile plot
        self.trace0 = self.plot(
            x=[], y=[],
            pen=pg.mkPen('black', width=3),
            symbol='o')
        self.setYRange(30, 110) # FIXME
        self.setLabel('left', 'Received Power')
        self.setLabel('bottom', 'Range Gate')
    
    def newRangeProfile(self, Pr:np.ndarray):
        self.trace0.setData(Pr)


class PlotVelocity(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        # speed history
        self.speed_trace = self.plot(
            x=[], y=[],
            pen=pg.mkPen('black', width=3),
            symbol='o')
        
        max_v = waveform.n_dg * waveform.d_speed / 2 # m/s
        self.setYRange(0, max_v)
        self.setXRange(-20, 0) # FIXME
        self.setLabel('bottom', 'Time / s')
        self.setLabel('left', '|Speed| / m/s')
        # highscore
        self.speed_template = '<span style="color: red; font-size: 16pt;">Highest speed: {: 4.1f} m/s</span>'
        self.speed_text = pg.TextItem(html=self.speed_template.format(0))
        self.speed_text.setPos(-14,4) # position in data coordinates (i.e., time and speed), FIXME
        self.addItem(self.speed_text)

    def newSpeeds(self, t:list, v:list):
        self.speed_trace.setData(x=t, y=v)
        self.speed_text.setHtml(self.speed_template.format(np.max(v)))


class PlotTargetMap(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        # persistent point cloud
        self.sc_points = pg.ScatterPlotItem(x=[], y=[])
        self.setAspectLocked()
        self.setYRange(0, 4, padding=0) # boresight, FIXME
        self.setXRange(-2, 2, padding=0) # left/right, FIXME
        self.addItem(self.sc_points)
        self.setLabel('bottom', 'X Position / m')
        self.setLabel('left', 'Y Position / m')

    def newPointCloud(self, spots):
        self.sc_points.setData(spots=spots)
