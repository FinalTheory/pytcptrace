import os
import sys
import json
import subprocess
from tempfile import NamedTemporaryFile

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
        pid = subprocess.Popen([self._tcptrace, '-J' + temp_name, pcap_file],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        pid.wait()
        if pid.returncode != 0:
            raise RuntimeError('tcptrace exited with return code %d' % pid.returncode)
        else:
            fid = open(temp_name, 'r')
            raw_json = fid.read()
            fid.close()
            os.remove(temp_name)
            return PcapHandle(raw_json, pid.stdout.read(), pid.stderr.read())


class PcapHandle:
    def __init__(self, raw_json, stdout, stderr):
        self._raw_json = raw_json.decode('utf-8')
        self._stdout = stdout
        self._stderr = stderr
        self.conn_data = json.loads(self._raw_json)

    def read(self, filter_func=None):
        if not filter_func:
            return self.conn_data
        else:
            return filter(lambda x: filter_func(x), self.conn_data)
