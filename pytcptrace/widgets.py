import Tkinter as tk
import ttk
import tkFont
import time
import datetime
import numpy as np
import matplotlib

matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure

__author__ = 'huangyan13@baidu.com'


class Widget:
    def __init__(self, master, title):
        self.master = master
        self.title = title
        self.window = None

    def activate(self, connections, selection):
        pass

    def _quit(self):
        if self.window:
            # stops mainloop
            self.window.quit()
            # this is necessary on Windows to prevent
            # Fatal Python Error: PyEval_RestoreThread: NULL tstate
            self.window.destroy()


class ThroughputGraph(Widget):
    def __init__(self, master):
        Widget.__init__(self, master, 'Throughput Graph')
        self.window = None

    def activate(self, connections, selection):
        window = tk.Toplevel(master=self.master)
        window.title(self.title)
        self.window = window

        # plot code here
        f = Figure(figsize=(10, 4))
        a = f.add_subplot(111)
        t = np.arange(0.0, 3.0, 0.01)
        s = np.sin(2 * np.pi * t)
        a.plot(t, s)

        f.tight_layout()

        # set canvas
        canvas = FigureCanvasTkAgg(f, master=window)
        canvas.show()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2TkAgg(canvas, window)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        button = tk.Button(master=window, text='Quit', command=self._quit)
        button.pack(side=tk.BOTTOM)
