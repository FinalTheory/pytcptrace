import Tkinter as tk
from pytcptrace import PyTcpTrace
from pytcptrace import ThroughputGraph, ConnectionData

__author__ = 'huangyan13@baidu.com'

if __name__ == '__main__':
    gui = PyTcpTrace(tk.Tk())
    gui.add_widget('Raw Data', ConnectionData)
    gui.add_widget('Throughput', ThroughputGraph)
    gui.mainloop()
