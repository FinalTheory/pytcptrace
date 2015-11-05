import Tkinter as tk
from container import PyTcpTrace

__author__ = 'huangyan13@baidu.com'

if __name__ == '__main__':
    gui = PyTcpTrace(tk.Tk())
    gui.mainloop()
