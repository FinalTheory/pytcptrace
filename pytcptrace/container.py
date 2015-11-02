import Tkinter as tk
from numpy import arange, sin, pi
import matplotlib

matplotlib.use('TkAgg')
from tkFileDialog import askopenfilename, asksaveasfilename
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure


class PyTcpTrace:
    def __init__(self, master):
        self.master = master
        master.title("tcptrace analyze")
        master.protocol("WM_DELETE_WINDOW", lambda: (master.quit(), master.destroy()))

        self.filename = tk.StringVar()
        self.prefix = tk.StringVar()
        self.filter_str = tk.StringVar()

        self.widget_list = []
        self.frame_list = []
        self.init_loadfile()
        self.init_filter()

    def init_loadfile(self):
        new_frame = tk.Frame(master=self.master)
        tk.Label(master=new_frame, text='File: ').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.filename).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Select',
                  command=lambda: self.filename.set(askopenfilename(title='Choose .pcap file'))).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Load').pack(side=tk.LEFT)
        new_frame.pack(side=tk.BOTTOM, fill=tk.BOTH)

        new_frame = tk.Frame(master=self.master)
        tk.Label(master=new_frame, text='Name Prefix').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.prefix).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Export All').pack(side=tk.LEFT)
        new_frame.pack(side=tk.BOTTOM, fill=tk.BOTH)

    def init_filter(self):
        new_frame = tk.Frame(master=self.master)
        tk.Label(master=new_frame, text='Filter: ').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.filter_str).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Apply').pack(side=tk.LEFT)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def add_widget(self, widget_type, *args, **kwargs):
        new_frame = tk.Frame(master=self.master)
        widget_obj = widget_type(new_frame, *args, **kwargs)
        self.widget_list.append(widget_obj)
        self.frame_list.append(new_frame)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def mainloop(self):
        self.master.mainloop()
