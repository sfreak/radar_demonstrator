#
# Config parser for TI mmw demo from mmWave SDK 1.2
#
# relevant quantities:
# * dimension of range-doppler heatmap
# * measurement bandwidth
# * active measurement time
# * cycle time

import math
from dataclasses import dataclass

@dataclass
class WaveformFOV:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

@dataclass
class Waveform:
    n_rg: int
    n_dg: int
    f_center: float
    d_range: float
    d_speed: float
    t_frame: float
    fov: WaveformFOV


def nextpow2(x):
    return 2**(math.ceil(math.log(x, 2)))


def parse_config(cfg_name:str):

    with open(cfg_name, 'r') as f:
        cfg = f.readlines()

    profile = [line.split() for line in cfg if 'profileCfg' in line][0]
    f_start = float(profile[2]) * 1e9
    t_idle = float(profile[3]) * 1e-6
    t_adcstart = float(profile[4]) * 1e-6
    t_rampend = float(profile[5]) * 1e-6
    slope = float(profile[8]) * 1e12
    n_samples = float(profile[10])
    f_sample = float(profile[11]) * 1e3

    frame = [line.split() for line in cfg if 'frameCfg' in line][0]
    i_chirp_start = float(frame[1])
    i_chirp_end = float(frame[2])
    n_loops = float(frame[3])
    n_frames = float(frame[4])
    t_frame = float(frame[5]) * 1e-3

    # SDK1.2 has no FOV config, so use custom lines
    fov_x = [line.split() for line in cfg if 'fov_x' in line][0]
    fov_x_min = float(fov_x[1])
    fov_x_max = float(fov_x[2])
    fov_y = [line.split() for line in cfg if 'fov_y' in line][0]
    fov_y_min = float(fov_y[1])
    fov_y_max = float(fov_y[2])
    fov = WaveformFOV(fov_x_min, fov_x_max, fov_y_min, fov_y_max)

    n_chirptypes = i_chirp_end - i_chirp_start + 1
    t_sample = n_samples / f_sample
    t_chirp = t_idle + t_rampend
    t_loop = t_chirp * n_chirptypes # assumes all chirp types are the same duration

    # center frequency
    f_center = f_start + (t_adcstart + t_sample/2) * slope
    wavelen = 3e8 / f_center

    # range resolution
    B = t_sample * slope
    d_range = 3e8 / 2 / B

    # Doppler resolution
    T = n_loops * t_loop # active measurement time within a radar cycle (i.e., CPI but including gaps)
    d_doppler = 1 / T # Hz
    d_speed = d_doppler * wavelen / 2 # m/s

    # range and doppler FFTs use padding if length is not a power of 2
    n_rg = nextpow2(n_samples)
    n_dg = nextpow2(n_loops)

    # RDM dimensions: n_rg * n_dg
    # range resolution: d_range
    # speed resolution: d_speed
    # cycle time: t_frame

    return Waveform(
        n_rg = int(n_rg),
        n_dg = int(n_dg),
        f_center = f_center,
        d_range = d_range,
        d_speed = d_speed,
        t_frame = t_frame,
        fov = fov
    )

    
if __name__ == '__main__':
    wf = parse_config('radar/profile_range_doppler.cfg')
    print(wf)