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

        self.waveform = waveform
        
        r_max = waveform.n_rg * waveform.d_range
        v_max = waveform.n_dg * waveform.d_speed / 2
        tr = QtGui.QTransform()
        tr.translate(0, -v_max) # move DG32 to 0
        tr.scale(
            waveform.d_range, # RG to m
            waveform.d_speed # DG to m/s
        )
        self.img.setTransform(tr) # assign transform
        self.img.setColorMap(pg.colormap.get('viridis'))

        self.setRange(yRange=(-v_max, v_max), xRange=(0, r_max), padding=0)
        self.addItem(self.img)

        self.setLabel('bottom', 'Range / m')
        self.setLabel('left', 'Radial Speed / m/s')

        # target list overlay on RDM
        self.sc = pg.ScatterPlotItem(x=[], y=[])
        self.addItem(self.sc)

    def newTargets(self, targets:list[dict]):
        # FIXME should this conversion be done Controller instead?
        r = [(t.get('rg')+0.5)*self.waveform.d_range for t in targets]
        v = [(t.get('dg')+0.5)*self.waveform.d_speed for t in targets]
        self.sc.setData(x=r, y=v)

    def newRDM(self, rdm:np.ndarray):
        imdata = np.fft.fftshift(rdm, axes=1)
        self.img.setImage(imdata)


class PlotRangeProfile(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        self.x = np.arange(waveform.n_rg) * waveform.d_range

        # Range profile plot
        self.trace0 = self.plot(
            x=[], y=[],
            pen=pg.mkPen('black', width=3),
            symbol='o')
        self.setYRange(30, 110) # FIXME
        self.setXRange(0, waveform.n_rg*waveform.d_range, padding=0)
        self.setLabel('left', 'Received Power / dB')
        self.setLabel('bottom', 'Range / m')
    
    def newRangeProfile(self, Pr:np.ndarray):
        self.trace0.setData(self.x, Pr)


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
        self.setLabel('left', '|Radial Speed| / m/s')
        # highscore
        # https://stackoverflow.com/a/70200326
        self.speed_template = 'Highest radial speed: {: 4.1f} m/s'
        self.speed_text = pg.LabelItem("Error", size="16pt", color="red")
        self.speed_text.setParentItem(self.getPlotItem())
        self.speed_text.anchor(itemPos=(0.5,0.5), parentPos=(0.5,0.2), offset=(0,0))

    def newSpeeds(self, t:list, v:list):
        self.speed_trace.setData(x=t, y=v)
        self.speed_text.setText(self.speed_template.format(np.max(v)))


class PlotTargetMap(PlotWidget):
    def __init__(self, waveform:Waveform, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

        # persistent point cloud
        self.sc_points = pg.ScatterPlotItem(x=[], y=[])
        self.setAspectLocked()
        self.setYRange(waveform.fov.x_min, waveform.fov.x_max) # boresight
        self.setXRange(waveform.fov.y_min, waveform.fov.y_max) # left/right
        self.addItem(self.sc_points)
        self.setLabel('bottom', 'X Position / m')
        self.setLabel('left', 'Y Position / m')

    def newPointCloud(self, spots):
        self.sc_points.setData(spots=spots)
