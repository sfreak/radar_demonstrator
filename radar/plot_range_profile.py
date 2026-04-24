import time
import logging
import matplotlib.pyplot as plt
import numpy as np
from radar.radar_helper import Radar, RadarResults, RadarTransmissionError


n_range_gates = 256  # do not change - set in profile.cfg

logging.basicConfig(level=logging.WARNING)

radar = Radar(
    com_ctrl='COM10',  # XDS110 Class Application/User UART
    com_data='COM9',  # XDS110 Class Auxiliary Data Port
    waveform_config='ti_rdm/profile_range.cfg'
)
print('Radar module initialized. Waiting for data...')

# create plot window
plt.ion()  # interactive mode allows dynamically updating plot contents
fig, ax = plt.subplots()
l_pr, = ax.plot([], [], color='red')
l_pn, = ax.plot([], [], color='gray')
ax.set_ylim([30, 100])  # fixed y scale, adjust for your environment
ax.set_xlim([0, n_range_gates])
ax.set_ylabel('Power (log)')
ax.set_xlabel('Range Bin')

plt.show(block=False)
bg = fig.canvas.copy_from_bbox(fig.bbox)

x = np.arange(n_range_gates)

while True:
    # read new radar data from serial port
    results = radar.read()
    pr = results.rangedata
    pn = results.noisedata

    t0 = time.perf_counter()
    fig.canvas.restore_region(bg)

    l_pr.set_xdata(x)
    l_pr.set_ydata(pr)

    l_pn.set_xdata(x)
    l_pn.set_ydata(pn)

    ax.draw_artist(l_pr)
    fig.canvas.blit(fig.bbox)
    fig.canvas.flush_events()
    t1 = time.perf_counter()
    logging.info(f'plot duration {(t1-t0)*1000:.1f} ms')
