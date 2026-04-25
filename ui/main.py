import sys
import logging
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QAction, QTabWidget, QVBoxLayout, QLabel, QGridLayout
from ui.view import PlotRangeProfile, PlotRDM, PlotTargetMap, PlotVelocity
from ui.model import Controller
from radar.parse_config import Waveform


class AppSingle(QMainWindow):
    def __init__(self, waveform:Waveform):
        super().__init__()
        self.title = 'Radar Viewer'
        self.left = 0
        self.top = 0
        self.width = 2000
        self.height = 1000
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName('gridLayout')

        self.tab1 = PlotRangeProfile(waveform=waveform)
        self.tab2 = PlotRDM(waveform=waveform)
        self.tab3 = PlotTargetMap(waveform=waveform)
        self.tab4 = PlotVelocity(waveform=waveform)

        self.gridLayout.addWidget(self.tab1, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.tab2, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.tab3, 0, 1, 3, 1)
        self.gridLayout.addWidget(self.tab4, 2, 0, 1, 1)

        self.mainWidget = QWidget()
        self.mainWidget.setLayout(self.gridLayout)

        self.setCentralWidget(self.mainWidget)
        self.show()


class AppTabs(QMainWindow):
    def __init__(self, waveform:Waveform):
        super().__init__()
        self.title = 'Radar Viewer'
        self.left = 0
        self.top = 0
        self.width = 2000
        self.height = 1000
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.tab_widget = QTabWidget(self)

        self.tab1 = PlotRangeProfile(waveform=waveform)
        self.tab2 = PlotRDM(waveform=waveform)
        self.tab3 = PlotTargetMap(waveform=waveform)
        self.tab4 = PlotVelocity(waveform=waveform)

        self.tab_widget.addTab(self.tab1, "Range Profile")
        self.tab_widget.addTab(self.tab2, "Range-Doppler Heatmap")
        self.tab_widget.addTab(self.tab3, "Target Grid")
        self.tab_widget.addTab(self.tab4, "Velocity")

        self.setCentralWidget(self.tab_widget)
        self.show()


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w')
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)

    app = QApplication(sys.argv)
    
    ctrl = Controller()
    wf = ctrl.getWaveform()
    
    if '--tabs' in sys.argv:
        ex = AppTabs(wf)
    else:
        ex = AppSingle(wf)

    ctrl.newRangeProfile.connect(ex.tab1.newRangeProfile)
    ctrl.newTargets.connect(ex.tab2.newTargets)
    ctrl.newRDM.connect(ex.tab2.newRDM)
    ctrl.newPointCloud.connect(ex.tab3.newPointCloud)
    ctrl.newSpeeds.connect(ex.tab4.newSpeeds)
    
    sys.exit(app.exec_())
