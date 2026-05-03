import sys
import logging
import signal
import PyQt5
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QAction, QTabWidget, QVBoxLayout, QLabel, QGridLayout, QDesktopWidget
from ui.view import PlotRangeProfile, PlotRDM, PlotTargetMap, PlotVelocity
from ui.model import Controller
from radar.parse_config import Waveform


class AppOne(QMainWindow):
    def __init__(self, waveform:Waveform):
        super().__init__()
        self.title = 'Radar Viewer 1'
        self.left = 0
        self.top = 0
        self.width = 800
        self.height = 600
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName('gridLayout')

        self.tab1 = PlotRangeProfile(waveform=waveform)
        self.tab2 = PlotRDM(waveform=waveform)
        self.tab3 = PlotVelocity(waveform=waveform)

        self.gridLayout.addWidget(self.tab1, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.tab2, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.tab3, 2, 0, 1, 1)

        self.mainWidget = QWidget()
        self.mainWidget.setLayout(self.gridLayout)

        self.setCentralWidget(self.mainWidget)
        self.showFullScreen()

class AppTwo(QMainWindow):
    def __init__(self, waveform:Waveform):
        super().__init__()
        self.title = 'Radar Viewer 2'
        self.left = 0
        self.top = 0
        self.width = 800
        self.height = 600
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName('gridLayout')

        self.tab1 = PlotTargetMap(waveform=waveform)

        self.gridLayout.addWidget(self.tab1, 0, 0, 1, 1)

        self.mainWidget = QWidget()
        self.mainWidget.setLayout(self.gridLayout)

        self.setCentralWidget(self.mainWidget)
        self.show()


def sigint_handler(signum, frame):
    '''Ask app to close if Ctrl+C is pressed.'''
    QApplication.quit()
    

if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w')
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)

    app = QApplication(sys.argv)

    signal.signal(signal.SIGINT, sigint_handler)
    
    ctrl = Controller()
    wf = ctrl.getWaveform()
    
    ex1 = AppOne(wf)
    ex2 = AppTwo(wf)

    # screen 1
    monitor = QDesktopWidget().screenGeometry(0)
    ex1.move(monitor.left(), monitor.top())
    ex1.showFullScreen()

    monitor = QDesktopWidget().screenGeometry(1)
    ex2.move(monitor.left(), monitor.top())
    ex2.showFullScreen()

    ctrl.newRangeProfile.connect(ex1.tab1.newRangeProfile)
    ctrl.newTargets.connect(ex1.tab2.newTargets)
    ctrl.newRDM.connect(ex1.tab2.newRDM)
    ctrl.newSpeeds.connect(ex1.tab3.newSpeeds)

    ctrl.newPointCloud.connect(ex2.tab1.newPointCloud)

    sys.exit(app.exec_())
