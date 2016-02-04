import os
import time
import base64
import datetime
import json
import subprocess
from tempfile import NamedTemporaryFile
from filter import generate_filter

__author__ = 'huangyan13@baidu.com'


class TcpTrace:
    def __init__(self):
        self._tcptrace = self._get_tcptrace()

    def _get_tcptrace(self):
        dirname, filename = os.path.split(os.path.abspath(__file__))
        tcptrace_path = os.path.join(dirname, 'tcptrace')
        if os.path.exists(tcptrace_path) and os.path.isfile(tcptrace_path):
            return tcptrace_path
        else:
            raise IOError('tcptrace executable not exist.')

    def open(self, pcap_file):
        fid = NamedTemporaryFile('w', delete=False)
        temp_name = fid.name
        fid.close()
        pid = subprocess.Popen([self._tcptrace, '-n', '-J' + temp_name, '-e', '-T', pcap_file],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        pid.wait()
        if pid.returncode != 0:
            raise RuntimeError('tcptrace exited with return code %d' % pid.returncode)
        else:
            fid = open(temp_name, 'r')
            raw_json = fid.read()
            fid.close()
            if not raw_json:
                raise RuntimeError('.pcap file do not contain valid TCP connections.')
            os.remove(temp_name)
            return PcapHandle(raw_json, pid.stdout.read(), pid.stderr.read())


class PcapHandle:
    # the unix timestamp of 2000-01-01
    TIME_MAGIC = time.mktime(datetime.datetime(2000, 1, 1).timetuple())

    def __init__(self, raw_json, stdout, stderr):
        self._raw_json = raw_json.decode('utf-8')
        self._stdout = stdout
        self._stderr = stderr
        self.conn_data = json.loads(self._raw_json)
        self.filter_func = None
        self.shift_time()
        self.decode_data()

    @staticmethod
    def decode_base64(data):
        """
            Decode base64, padding being optional.
            :param data: Base64 data as an ASCII byte string
            :returns: The decoded byte string.
        """
        missing_padding = 4 - len(data) % 4
        if missing_padding:
            data += b'=' * missing_padding
        return base64.decodestring(data)

    def decode_data(self):
        for idx in range(len(self.conn_data)):
            for field in ('a2b', 'b2a'):
                if 'base64_data' in self.conn_data[idx][field]:
                    self.conn_data[idx][field]['base64_data'] =\
                        self.decode_base64(self.conn_data[idx][field]['base64_data'])

    def shift_time(self):
        min_time = None
        for conn in self.conn_data:
            times = (conn['first_packet_time'],
                     conn['a2b']['first_data_time'][0],
                     conn['b2a']['first_data_time'][0])
            for t in times:
                if t > self.TIME_MAGIC and (not min_time or t < min_time):
                    min_time = t

        def time_wrapper(time_val):
            return time_val if time_val < self.TIME_MAGIC else time_val - min_time

        for idx in range(len(self.conn_data)):
            for field in ('first_packet_time', 'last_packet_time'):
                self.conn_data[idx][field] = time_wrapper(self.conn_data[idx][field])

            for direct in ('a2b', 'b2a'):
                for field in ('first_data_time', 'last_data_time'):
                    self.conn_data[idx][direct][field][0] = time_wrapper(self.conn_data[idx][direct][field][0])

                for field in ('time', 'points_time'):
                    if field in self.conn_data[idx][direct]:
                        for i in range(len(self.conn_data[idx][direct][field])):
                            self.conn_data[idx][direct][field][i] = time_wrapper(self.conn_data[idx][direct][field][i])

    def set_filter(self, filter_func=None):
        self.filter_func = filter_func

    def read(self):
        if not self.filter_func:
            return self.conn_data
        else:
            return filter(lambda x: self.filter_func(x), self.conn_data)
