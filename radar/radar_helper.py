import numpy as np
import serial
import struct
import os
import logging
import queue
import threading
import time


class RadarTransmissionError(Exception):
    pass


class RadarResults:
    pass


class Radar:
    # magic word start marks the start of a data packet
    magic = b'\x02\x01\x04\x03\x06\x05\x08\x07'

    magic_len = 8
    header_len = 8 * 4

    tags = {
        1: 'MMWDEMO_OUTPUT_MSG_DETECTED_POINTS',
        2: 'MMWDEMO_OUTPUT_MSG_RANGE_PROFILE',
        3: 'MMWDEMO_OUTPUT_MSG_NOISE_PROFILE',
        4: 'MMWDEMO_OUTPUT_MSG_AZIMUT_STATIC_HEAT_MAP',
        5: 'MMWDEMO_OUTPUT_MSG_RANGE_DOPPLER_HEAT_MAP',
        6: 'MMWDEMO_OUTPUT_MSG_STATS',
    }

    def __init__(self, com_ctrl, com_data, waveform_config='profile.cfg', send_config=True, reset=True):

        self.logger = logging.getLogger(self.__class__.__name__)

        self.decoded_data = {}

        self.ser_ctrl = serial.Serial(port=com_ctrl, baudrate=115200, timeout=0.1)

        if reset:
            os.system(r'C:\ti\ccs1271\ccs\ccs_base\common\uscif\xds110\xds110reset.exe')

        if send_config:
            self._send_config(waveform_config)

        self.com_queue = queue.Queue(-1)
        self.com_stop = threading.Event()
        self.com_thread = threading.Thread(target=self._read_serial, args=(
            com_data, self.com_queue, self.com_stop, ))
        self.com_thread.start()

        self.ser_ctrl.write(b'sensorStart\n')
        response = self.ser_ctrl.read(1024)
        print(response.decode(errors='replace'), end='')
        
    def _send_config(self, configfile):
        """Transmits config file to AWR1642BOOST via CLI interface to setup chirps etc.

        :param configfile: filename (str) of CLI configuration
        """

        with open(configfile, "rb") as cf:
            config = cf.readlines()

        print()
        print("Chirp configuration:")
        response = self.ser_ctrl.read(1024)
        print(response.decode(errors='replace'), end='')
        for l in config:
            line = l.strip()
            if line.startswith(b'%'): continue
            self.ser_ctrl.write(line + b'\n')
            echo = self.ser_ctrl.readline()
            response = self.ser_ctrl.readline()
            time.sleep(0.001)
            print(echo.decode(errors='replace'), end='')
            print(response.decode(errors='replace'), end='')
            if b'Done' not in response:
                raise Exception('Radar sensor reported error:' + response.decode(errors='replace'))
        print()
        print()

    def _read_serial(self, com_data, com_queue, stop_evt):

        synchronized = False

        ser_data = serial.Serial(com_data, 921600, timeout=5)
        ser_data.flush()

        while not stop_evt.isSet():

            if synchronized:
                header = ser_data.read(self.magic_len + self.header_len)
            else:
                # read and discard bytes until we find the magic sequence
                buf = ser_data.read(8)
                i = 0
                while buf != self.magic:
                    buf = buf[1:] + ser_data.read(1)
                    i += 1
                    if i % 1000 == 0:
                        self.logger.warning(f'_read_serial lost sync, {i} bytes discarded')

                header = buf + ser_data.read(self.header_len)
                self.logger.warning(f'_read_serial reacquired sync after discarding {i} bytes')

            if header[:self.magic_len] == self.magic:
                synchronized = True
            else:
                self.logger.warning(f'header mismatch: {header[:8]} expected {self.magic}')
                synchronized = False
                continue

            packet_len = struct.unpack('<I', header[12:16])[0]
            self.logger.info(f'totalpacketlen {packet_len}')
            body_len = packet_len - self.magic_len - self.header_len
            body = ser_data.read(body_len)
            com_queue.put(header+body)

        ser_data.close()

    def read(self):
        results = None

        # try reading radar results
        # if there is a transmission error, ignore and retry until successful
        while results is None:
            try:
                data = self.com_queue.get()
                results = self.parse_packet(data)
            except RadarTransmissionError as e:
                print('Discarding incomplete packet.')
                pass

        return results

    def parse_packet(self, data):
        i = 8 # skip magic as it has already been checked

        self.decoded_data = {}

        # parse header
        version, totalPacketLen, platform, frameNumber, timeCpuCycles, numDetectedObj, numTLVs, subFrameNumber = \
            struct.unpack('<IIIIIIII', data[i:(i+self.header_len)])

        self.logger.info("version: {}.{}.{}.{}".format(
             (version >> 24) & 0xFF,
             (version >> 16) & 0xFF,
             (version >> 8) & 0xFF,
             version & 0xFF
         ))
        self.logger.info("totalPacketLen: {}".format(totalPacketLen))
        self.logger.info("platform:       {}".format(platform))
        self.logger.info("frameNumber:    {}".format(frameNumber))
        self.logger.info("timeCpuCycles:  {}".format(timeCpuCycles))
        self.logger.info("numDetectedObj: {}".format(numDetectedObj))
        self.logger.info("numTLVs:        {}".format(numTLVs))
        self.logger.info("subFrameNumber: {}".format(subFrameNumber))

        #print('buffer length:  {}'.format(len(data)))

        if len(data) != totalPacketLen:
            # check the number of bytes in our buffer match the packet length according to its header
            raise RadarTransmissionError('!!! Invalid packet size {}, expected {}. Discarding packet !!!'.format(len(data), totalPacketLen-8))

        i += self.header_len

        results = RadarResults()

        # after the header, multiple data blocks (TLVs) follow
        for tlv_idx in range(numTLVs):

            tlv_headersize = 4 + 4
            tlv_tag, tlv_len = struct.unpack('<II', data[i:(i+tlv_headersize)])

            self.logger.info('TLV {}: tag {} len {}'.format(tlv_idx, tlv_tag, tlv_len))

            #assert(tlv_tag <= max(self.tags.keys()))

            tlv_data = data[i+tlv_headersize:i+tlv_headersize+tlv_len]

            if tlv_tag == 1:
                # MMWDEMO_OUTPUT_MSG_DETECTED_POINTS

                tgt_header = tlv_data[:4]
                tgt_body = tlv_data[4:]
                n_obj, qformat = struct.unpack('<HH', tgt_header)
                self.logger.info('DETECTED_POINTS: %d %d', n_obj, qformat)
                offs = 0
                targets = []
                for tgt in range(n_obj):
                    rg, dg, pk, x, y, z = struct.unpack('<HhHhhh', tgt_body[offs:offs+12])
                    x = x / 2**qformat
                    y = y / 2**qformat
                    z = z / 2**qformat
                    self.logger.info('tgt %02d: % 4d % 4d % 6d %7.3f %7.3f %7.3f', tgt, rg, dg, pk, x, y, z)
                    offs += 12
                    target = {
                        'rg': rg,
                        'dg': dg,
                        'peakval': pk,
                        'x': x,
                        'y': y,
                        'z': z,
                    }
                    targets.append(target)
                results.targets = targets

            elif tlv_tag == 2:
                # range profile
                rangedata = np.frombuffer(tlv_data, dtype='<u2').astype(float)
                # data format lof log2, Q8
                rangedata /= 256
                rangedata /= np.log2(10)
                rangedata *= 2  # voltage to power
                results.rangedata = rangedata

            elif tlv_tag == 3:
                # noise profile
                noisedata = np.frombuffer(tlv_data, dtype='<u2').astype(float)
                noisedata /= 256
                noisedata /= np.log2(10)
                noisedata *= 2  # voltage to power
                results.noisedata = noisedata

            elif tlv_tag == 5: 
                # MMWDEMO_OUTPUT_MSG_RANGE_DOPPLER_HEAT_MAP
                # Length: (Range FFT size) x (Doppler FFT size) (size of uint16_t)

                """  SDK 0.8:
                    /* This EDMA channel copes the sum (across virtual antennas) of log2
                        * magnitude squared of Doppler FFT bins from L2 mem to detection
                        * matrix in L3 mem */"""
                rdm = np.frombuffer(tlv_data, dtype='<u2')
                rdm = np.array(rdm, dtype=float)
                rdm /= 256 # Q8 format, i.e. 8 fractional bits 
                rdm /= np.log2(10) # to log10
                rdm *= 2 # voltage to power FIXME: description above sounds like this is not needed...
                #rdm = np.reshape(rdm, [self.config_rangeBins, self.config_dopplerBins])
                rdm = np.reshape(rdm, [128, 64])
                results.range_doppler_heatmap = rdm

            elif tlv_tag == 6:  # MMWDEMO_OUTPUT_MSG_STATS
                interFrameProcessingTime, transmitOutputTime, interFrameProcessingMargin, interChirpProcessingMargin, \
                    activeFrameCPULoad, interFrameCPULoad = struct.unpack('<IIIIII', tlv_data)

                self.logger.info('interFrameProcessingTime    {} us'.format(interFrameProcessingTime))
                self.logger.info('transmitOutputTime          {} us'.format(transmitOutputTime))
                self.logger.info('interFrameProcessingMargin  {} us'.format(interFrameProcessingMargin))
                self.logger.info('interChirpProcessingMargin  {} us'.format(interChirpProcessingMargin))
                self.logger.info('activeFrameCPULoad          {}'.format(activeFrameCPULoad))
                self.logger.info('interFrameCPULoad           {}'.format(interFrameCPULoad))
            
            else:
                self.logger.warning('TLV idx {} tag {} not handled'.format(tlv_idx, tlv_tag))

            i += tlv_len + 8

        return results
