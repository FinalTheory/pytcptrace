import Tkinter as tk
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
from scipy.interpolate import interp1d
from tkMessageBox import showerror

__author__ = 'huangyan13@baidu.com'


class Widget:
    def __init__(self, master, title):
        self.master = master
        self.title = title
        self.window = None
        self.connections = None
        self.selection = None
        self.is_active = False

    def activate(self, connections, selection):
        window = tk.Toplevel(master=self.master)
        window.protocol("WM_DELETE_WINDOW", self.window_close)
        window.title(self.title)
        self.window = window
        self.connections = connections
        self.selection = selection
        self.is_active = True

    def window_close(self):
        if self.window:
            self.window.destroy()
            self.window = None
            self.connections = None
            self.selection = None
            self.is_active = False


class ThroughputGraph(Widget):
    def __init__(self, master):
        Widget.__init__(self, master, 'Throughput Graph')
        self.is_active = False
        self.figure = None
        self.aver_window = tk.StringVar()
        self.aver_window.set('0.2')
        self.smooth = tk.IntVar()

    def smoothing(self, x_val, y_val):
        if not x_val or not y_val:
            return np.array([]), np.array([])
        x_val = np.array(x_val)
        y_val = np.array(y_val)
        new_x = np.linspace(x_val[0], x_val[-1], num=len(x_val)*10)
        func = interp1d(x_val, y_val, kind='cubic')
        new_y = func(new_x)
        new_y[new_y < 0] = 0
        return new_x, new_y

    def instant_average(self, t, val, aver_window):
        x_val = []
        y_val = []
        prev_idx = 0
        cumsum = np.cumsum(val)
        for i in xrange(1, len(t)):
            if t[i] - t[prev_idx] > aver_window:
                x_val.append((t[i] + t[prev_idx]) / 2.)
                y_val.append((cumsum[i] - cumsum[prev_idx]) / (t[i] - t[prev_idx]))
                prev_idx = i
        if self.smooth.get():
            return self.smoothing(x_val, y_val)
        else:
            return np.array(x_val), np.array(y_val)

    def total_average(self, t, val, aver_window):
        x_val = []
        y_val = []
        prev_idx = 0
        cumsum = np.cumsum(val)
        for i in xrange(1, len(t)):
            if t[i] - t[prev_idx] > aver_window:
                x_val.append((t[i] + t[prev_idx]) / 2.)
                y_val.append((cumsum[i] - cumsum[0]) / (t[i] - t[0]))
                prev_idx = i
        if self.smooth.get():
            return self.smoothing(x_val, y_val)
        else:
            return np.array(x_val), np.array(y_val)

    def plot_data(self, plot_type):
        # first clear the figure
        self.figure.clf()

        # plot code here
        axis = self.figure.add_subplot(111)
        idx2name = {
            1: 'a2b',
            2: 'b2a',
        }
        for select in self.selection:
            if select[1] != 0:
                conn = self.connections[select[0]]
                title_l = '%s:%d' % (conn['host_a'], conn['port_a'])
                title_r = '%s:%d' % (conn['host_b'], conn['port_b'])
                if select[1] == 1:
                    title = title_l + ' -> ' + title_r
                else:
                    title = title_r + ' -> ' + title_l
                sub_conn = self.connections[select[0]][idx2name[select[1]]]
                t = np.array(sub_conn['points_time'])
                val = np.array(sub_conn['points_data'])
                aver_window = float(self.aver_window.get())

                def set_axis(ax):
                    ax.legend(loc='upper right')
                    ax.set_xlabel('Time (s)')
                    ax.set_ylabel('Throughput (Bytes/s)')

                if len(t) and len(val):
                    if plot_type == 'instant':
                        x_val, y_val = self.instant_average(t, val, aver_window)
                        if len(x_val) > 1:
                            axis.plot(x_val, y_val, label=title)
                            axis.set_title('Instant Throughput')
                            set_axis(axis)
                    elif plot_type == 'average':
                        x_val, y_val = self.total_average(t, val, aver_window)
                        if len(x_val) > 1:
                            axis.plot(x_val, y_val, label=title)
                            axis.set_title('Cumulative Average Throughput')
                            set_axis(axis)
                    else:
                        raise ValueError('Unknown plot type')

        # set tight layout for output
        self.figure.tight_layout()
        self.figure.canvas.draw()

    def init_buttons(self):
        new_frame = tk.Frame(master=self.window)
        tk.Label(master=new_frame, text='Average Scale').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.aver_window, width=4).pack(side=tk.LEFT)
        tk.Checkbutton(master=new_frame, text="Smoothing", variable=self.smooth).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Instant',
                  command=lambda: self.plot_data('instant')).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Average',
                  command=lambda: self.plot_data('average')).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Quit', command=self.window_close).pack(side=tk.LEFT)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def init_canvas(self):
        new_frame = tk.Frame(master=self.window)

        # configure canvas
        canvas = FigureCanvasTkAgg(self.figure, master=new_frame)
        canvas.show()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # configure toolbar
        toolbar = NavigationToolbar2TkAgg(canvas, new_frame)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def activate(self, connections, selection):
        if self.is_active:
            return
        Widget.activate(self, connections, selection)

        # proceed the selection items
        # leave only the sub-connections
        new_selection = []
        for select in self.selection:
            if select[1] == 0:
                if [select[0], 1] not in self.selection:
                    new_selection.append([select[0], 1])
                if [select[0], 2] not in self.selection:
                    new_selection.append([select[0], 2])
            else:
                new_selection.append(select)

        self.selection = new_selection
        self.figure = Figure(figsize=(15, 5))
        self.init_canvas()
        self.init_buttons()
        try:
            self.plot_data('instant')
        except:
            self.window_close()
            showerror('Error', 'Connection data could not be visualized.')


class ConnectionData(Widget):
    def __init__(self, master):
        Widget.__init__(self, master, 'Connection Raw Data')
        self.listbox = None
        self.text = None

    def init_interface(self):
        new_frame = tk.Frame(master=self.window)

        self.listbox = tk.Listbox(master=new_frame)
        self.text = tk.Text(master=new_frame)

        self.listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.text.pack(side=tk.RIGHT)

        new_frame.pack(side=tk.TOP)

    def show_text(self):
        pass

    def activate(self, connections, selection):
        if self.is_active:
            return
        Widget.activate(self, connections, selection)

        self.init_interface()

        for select in selection:
            pass


class HttpDetail(Widget):
    pass


class TimeSequenceGraph(Widget):
    pass

