import ttk
import tkFont
import inspect
import Tkinter as tk
import StringIO
from PIL import Image, ImageTk
import numpy as np
import curses.ascii
import FileDialog
import matplotlib
import magic
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
from scipy.interpolate import interp1d
from tkMessageBox import showerror, showinfo

from http_parser import HttpParser


__author__ = 'huangyan13@baidu.com'


class Widget(object):
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

    # leave only the sub-connections
    @staticmethod
    def selection_filter(selection):
        new_selection = []
        for select in selection:
            if select[1] == 0:
                if [select[0], 1] not in selection:
                    new_selection.append([select[0], 1])
                if [select[0], 2] not in selection:
                    new_selection.append([select[0], 2])
            else:
                new_selection.append(select)
        return new_selection


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

        new_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def activate(self, connections, selection):
        if self.is_active:
            return
        Widget.activate(self, connections, selection)
        # proceed the selection items
        self.selection = self.selection_filter(self.selection)
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
        self.preview_size = tk.IntVar()
        self.preview_size.set(4)
        self.str2conn = {}

    def init_interface(self):
        main_frame = tk.Frame(master=self.window)

        listbox_frame = tk.Frame(master=main_frame)

        new_frame = tk.Frame(master=listbox_frame)
        scrollbar1 = tk.Scrollbar(master=new_frame, orient=tk.VERTICAL)
        scrollbar2 = tk.Scrollbar(master=new_frame, orient=tk.HORIZONTAL)
        self.listbox = tk.Listbox(master=new_frame, font='Monaco',
                                  yscrollcommand=scrollbar1.set,
                                  xscrollcommand=scrollbar2.set)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        scrollbar1.config(command=self.listbox.yview)
        scrollbar2.config(command=self.listbox.xview)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        sub_frame = tk.Frame(master=listbox_frame)
        tk.Label(master=sub_frame, text='Preview Size').pack(side=tk.LEFT)
        tk.Entry(master=sub_frame, textvariable=self.preview_size, width=5).pack(side=tk.LEFT)
        tk.Label(master=sub_frame, text='KB').pack(side=tk.LEFT)
        sub_frame.pack(side=tk.TOP)

        listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        new_frame = tk.Frame(master=main_frame)
        scrollbar1 = tk.Scrollbar(master=new_frame, orient=tk.VERTICAL)
        scrollbar2 = tk.Scrollbar(master=new_frame, orient=tk.HORIZONTAL)
        self.text = tk.Text(master=new_frame, font='Monaco',
                            yscrollcommand=scrollbar1.set,
                            xscrollcommand=scrollbar2.set)
        scrollbar1.config(command=self.text.yview)
        scrollbar2.config(command=self.text.xview)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(fill=tk.BOTH, expand=True)
        new_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        main_frame.pack(fill=tk.BOTH, expand=True)

    def init_listbox(self):
        col_width = 0
        for select in self.selection:
            conn = self.connections[select[0]]
            if select[1] == 1:
                str_item = '%s:%d -> %s:%d' % (conn['host_a'], conn['port_a'],
                                               conn['host_b'], conn['port_b'])
                self.str2conn[str_item] = conn['a2b']

            else:
                str_item = '%s:%d -> %s:%d' % (conn['host_b'], conn['port_b'],
                                               conn['host_a'], conn['port_a'])
                self.str2conn[str_item] = conn['b2a']
            self.listbox.insert(tk.END, str_item)
            # increase column width
            new_w = len(str_item)
            if new_w > col_width:
                self.listbox.config(width=new_w)
                col_width = new_w

    def on_select(self, event):
        listbox = event.widget
        index = int(listbox.curselection()[0])
        sub_conn = self.str2conn[listbox.get(index)]
        # first delete all previous data
        self.text.delete(1.0, tk.END)
        # then insert real data into it
        if 'base64_data' in sub_conn:
            data = sub_conn['base64_data'].replace('\r\n', '\n')
            max_len = min(len(data), self.preview_size.get() * 1024)
            new_data = ''.join(map(lambda c:
                                   c if curses.ascii.isprint(c) or curses.ascii.isspace(c)
                                   else '\\x%X' % ord(c), list(data[0:max_len])))
            self.text.insert(tk.END, new_data)

    def activate(self, connections, selection):
        if self.is_active:
            return
        Widget.activate(self, connections, selection)
        # proceed the selection items
        self.selection = self.selection_filter(self.selection)
        self.init_interface()
        self.init_listbox()


class HttpDetail(Widget):
    ON_REQUEST = 0
    ON_RESPONSE = 1

    def _sort_func_default(self, x):
        return self.connections[x[0]]['first_packet_time']

    def __init__(self, master):
        self.Headers = [
            ('Method', self._sort_func_default),
            ('Host', self._sort_func_default),
            ('Path', self._sort_func_default),
            ('Start', self._sort_func_default),
            ('Stop', lambda x: self.connections[x[0]]['last_packet_time']),
            ('Total', lambda x: self.connections[x[0]]['elapsed_time']),
        ]
        Widget.__init__(self, master, 'HTTP Details')
        self.listbox = None
        self.text = None
        self.preview_size = tk.IntVar()
        self.preview_size.set(1)
        self.cursor = 0
        self.preview_status = self.ON_REQUEST
        self.request_list = None
        self.response_list = None
        self.connection_list = None
        self.sort_status = {}

    @staticmethod
    def selection_filter(selection):
        new_selection = []
        for select in selection:
            if select[1] == 1 or select[1] == 2:
                if [select[0], 0] not in selection:
                    new_selection.append([select[0], 0])
            else:
                new_selection.append(select)
        return new_selection
    
    def init_interface(self):
        main_frame = tk.Frame(master=self.window)

        listbox_frame = tk.LabelFrame(master=main_frame, text='List')
        
        new_frame = tk.Frame(master=listbox_frame)
        scrollbar1 = tk.Scrollbar(master=new_frame, orient=tk.VERTICAL)
        scrollbar2 = tk.Scrollbar(master=new_frame, orient=tk.HORIZONTAL)
        self.listbox = ttk.Treeview(master=new_frame,
                                    columns=map(lambda x: x[0], self.Headers),
                                    show="headings",
                                    yscrollcommand=scrollbar1.set,
                                    xscrollcommand=scrollbar2.set)
        scrollbar1.config(command=self.listbox.yview)
        scrollbar2.config(command=self.listbox.xview)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.listbox.bind('<<TreeviewSelect>>', self.on_select)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        listbox_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        for header, func in self.Headers:
            # set header for each column
            self.listbox.heading(header, text=header,
                                 command=lambda f=func, h=header: self.sort_by(f, h))

        text_frame = tk.LabelFrame(master=main_frame, text='Details')

        btn_frame = tk.Frame(master=text_frame)
        tk.Button(master=btn_frame, text='Request',
                  command=lambda: self.show('request')).pack(side=tk.LEFT)
        tk.Button(master=btn_frame, text='Response',
                  command=lambda: self.show('response')).pack(side=tk.LEFT)
        tk.Label(master=btn_frame, text='KB').pack(side=tk.RIGHT)
        tk.Entry(master=btn_frame, textvariable=self.preview_size, width=5).pack(side=tk.RIGHT)
        tk.Label(master=btn_frame, text='Preview Size').pack(side=tk.RIGHT)
        btn_frame.pack(side=tk.TOP)

        scrollbar1 = tk.Scrollbar(master=text_frame, orient=tk.VERTICAL)
        scrollbar2 = tk.Scrollbar(master=text_frame, orient=tk.HORIZONTAL)
        self.text = tk.Text(master=text_frame, font='Monaco',
                            yscrollcommand=scrollbar1.set,
                            xscrollcommand=scrollbar2.set)
        scrollbar1.config(command=self.text.yview)
        scrollbar2.config(command=self.text.xview)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(fill=tk.BOTH, expand=True)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        main_frame.pack(fill=tk.BOTH, expand=True)
    
    def sort_by(self, func, header):
        if self.connections:
            if header in ('Method', 'Path', 'Host'):
                header = 'Start'

            if header not in self.sort_status:
                self.sort_status[header] = False
            self.selection = sorted(self.selection, key=func,
                                    reverse=self.sort_status[header])
            self.update_treeview()
            self.sort_status[header] = not self.sort_status[header]

    @staticmethod
    def parse_http_list(raw_data):
        result_list = []
        start = 0
        end = len(raw_data)
        while start < end:
            r = HttpParser(decompress=True)
            ret = r.execute(raw_data[start:])
            if ret < 0:
                break
            start += ret
            result_list.append(r)

        return result_list

    def update_treeview(self):
        # clear previous status
        self.request_list = []
        self.response_list = []
        self.connection_list = []
        for iid in self.listbox.get_children():
            self.listbox.delete(iid)
        
        key_map = {
            'a2b': 'b2a',
            'b2a': 'a2b',
        }
        num_unknown = 0
        for select in self.selection:
            conn = self.connections[select[0]]
            found = False
            for key in ('a2b', 'b2a'):
                sub_conn = conn[key]
                data = sub_conn.get('base64_data', '')
                other_data = conn[key_map[key]].get('base64_data', '')
                # this is a response
                if data[0:4] == 'HTTP':
                    try:
                        req = self.parse_http_list(other_data)
                        reply = self.parse_http_list(data)
                    except RuntimeError:
                        continue
                    if len(req) == 0 or len(reply) == 0:
                        continue
                    self.request_list.append(req)
                    self.response_list.append(reply)
                    self.connection_list.append(conn)
                    found = True
            if not found:
                num_unknown += 1
        showinfo('Loading Complete', 'Non-HTTP Connection: %d' % num_unknown)

        data_list = [map(lambda x: x[0], self.Headers)]
        # first fill content into each row
        for idx, req in enumerate(self.request_list):
            conn = self.connection_list[idx]
            data = (req[0].get_method(), req[0].get_headers()['Host'],
                    req[0].get_url(), '%.2f' % conn['first_packet_time'],
                    '%.2f' % conn['last_packet_time'], '%.2f' % conn['elapsed_time'])
            self.listbox.insert('', tk.END, str(idx), values=data)
            data_list.append(data)

        # then adjust column width
        for idx, header in enumerate(map(lambda x: x[0], self.Headers)):
            # calculate max length
            len_list = map(lambda x: tkFont.Font().measure(x[idx].title()) + 10, data_list)
            if len(len_list) == 0:
                break
            elif len(len_list) == 1:
                max_len = len_list[0]
            else:
                max_len = max(*len_list)
            if header == 'Path' and max_len > 500:
                max_len = 500
            self.listbox.column(header, width=max_len)

    def show(self, show_type='request'):
        self.text.delete(1.0, tk.END)
        try:
            idx = int(self.listbox.selection()[0])
        except ValueError:
            return
        if show_type == 'request':
            self.preview_status = self.ON_REQUEST
            data = self.request_list[idx]
        else:
            self.preview_status = self.ON_RESPONSE
            data = self.response_list[idx]
        self.show_headers(data, show_type)

    def show_headers(self, data, show_type):
        for r in data:
            self.text.insert(tk.END, '<' * 20 + '-' * 20 + '>' * 20 + '\n\n')
            if show_type == 'request':
                self.text.insert(tk.END, ' '.join([r.get_method(), r.get_url(),
                                                   'HTTP/' + '.'.join(map(str, r.get_version()))]) + '\n\n', 'head')
            else:
                self.text.insert(tk.END, ' '.join(['HTTP/' + '.'.join(map(str, r.get_version())),
                                                   str(r.get_status_code()), r.get_reason()]) + '\n\n', 'head')
            raw_content = r.get_body()
            headers = r.get_headers()
            for key, val in headers.items():
                self.text.insert(tk.END, key + ': ', 'key')
                self.text.insert(tk.END, val + '\n')

            content = headers.get('Content-Type')
            self.text.insert(tk.END, '-' * 40 + '\n')
            if content:
                if content.split('/')[0].lower() == 'image':
                    img = Image.open(StringIO.StringIO(raw_content))
                    photo = ImageTk.PhotoImage(img)
                    label = tk.Label(self.text, image=photo)
                    label.photo = photo
                    self.text.window_create(tk.END, window=label)
                    self.text.insert(tk.END, '\n')
                else:
                    type_str = magic.from_buffer(raw_content)
                    if type_str[:5] == 'ASCII':
                        max_len = 1024 * self.preview_size.get()
                        display_str = raw_content[:min(max_len, len(raw_content))]
                        self.text.insert(tk.END, display_str)
                        if len(raw_content) > max_len:
                            button = tk.Button(self.text, text="More..",
                                               command=lambda d=raw_content: self.show_more(d))
                            self.text.window_create(tk.END, window=button)
                        self.text.insert(tk.END, '\n')
                    else:
                        self.text.insert(tk.END, type_str + '\n', 'type')
            self.text.insert(tk.END, '\n')
        self.text.tag_configure("key", foreground="blue")
        self.text.tag_configure("type", foreground="green")
        self.text.tag_configure("head", foreground="red")

    def show_more(self, data):
        dt_len = len(data)
        preview_len = self.preview_size.get() * 1024
        direction_up = 0
        direction_down = 1
        self.cursor = 0

        top = tk.Toplevel(self.master)
        top.title('Data Detail')

        text_frame = tk.Frame(master=top)
        scrollbar = tk.Scrollbar(master=text_frame, orient=tk.VERTICAL)
        text = tk.Text(master=text_frame, font='Monaco',
                       yscrollcommand=scrollbar.set)
        scrollbar.config(command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        text.insert(tk.END, data[0: min(preview_len, dt_len)])

        def move(direction):
            if direction == direction_up:
                self.cursor = max(0, self.cursor - preview_len)
            else:
                self.cursor = min(dt_len, self.cursor + preview_len)
            text.delete(1.0, tk.END)
            text.insert(tk.END, data[self.cursor: min(dt_len, self.cursor + preview_len)])

        btn_frame = tk.Frame(master=top)
        tk.Button(master=btn_frame, text='Up',
                  command=lambda d=direction_up: move(d)).pack(side=tk.LEFT)
        tk.Button(master=btn_frame, text='Down',
                  command=lambda d=direction_down: move(d)).pack(side=tk.RIGHT)
        btn_frame.pack(side=tk.TOP)

    def on_select(self, event):
        # first delete all previous data
        self.text.delete(1.0, tk.END)
        # then call function to update view
        if self.preview_status == self.ON_REQUEST:
            self.show('request')
        else:
            self.show('response')

    def activate(self, connections, selection):
        if self.is_active:
            return
        Widget.activate(self, connections, selection)
        # proceed the selected items
        self.selection = self.selection_filter(self.selection)
        self.init_interface()
        self.sort_by(self._sort_func_default, 'Start')


class TimeSequenceGraph(Widget):
    pass
