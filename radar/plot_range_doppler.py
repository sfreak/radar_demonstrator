import logging
import matplotlib.pyplot as plt
import numpy as np
import time
from radar.radar_helper import Radar, RadarResults, RadarTransmissionError


n_range_gates = 128  # do not change - set in profile.cfg
n_doppler_gates = 64 # do not change - set in profile.cfg

logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w')
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

radar = Radar(
    com_ctrl='COM10',  # XDS110 Class Application/User UART
    com_data='COM9',  # XDS110 Class Auxiliary Data Port
    waveform_config='ti_rdm/profile_range_doppler.cfg'
)
print('Radar module initialized. Waiting for data...')

# create plot window
plt.ion()  # interactive mode allows dynamically updating plot contents
fig, ax = plt.subplots()
im = ax.imshow(np.zeros((n_range_gates, n_doppler_gates)), vmin=40, vmax=100, aspect='auto', interpolation='nearest')
ax.set_ylabel('Doppler Bin')
ax.set_xlabel('Range Bin')
fig.colorbar(im)

plt.show(block=False)
bg = fig.canvas.copy_from_bbox(fig.bbox)

tprev = time.perf_counter()
while True:
    tr = time.perf_counter()
    # read new radar data from serial port
    results = radar.read()
    logging.info(f'radar data rx duration {(tr-tprev)*1000:.1f} ms')
    tprev = tr

    pr = results.range_doppler_heatmap
    imdata = np.fft.fftshift(pr, axes=1)

    t0 = time.perf_counter()
    fig.canvas.restore_region(bg)
    im.set_data(imdata)
    ax.draw_artist(im)
    fig.canvas.blit(fig.bbox)
    fig.canvas.flush_events()
    t1 = time.perf_counter()
    logging.info(f'plot duration {(t1-t0)*1000:.1f} ms')
