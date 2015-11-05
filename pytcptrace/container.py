# encoding: utf-8
import Tkinter as tk
import ttk
import tkFont
from pytcptrace import TcpTrace
from filter import generate_filter
from tkFileDialog import askopenfilename
from tkMessageBox import showerror


class PyTcpTrace:
    def __init__(self, master):
        self.master = master
        master.title("TCPtrace Analyze")
        master.protocol("WM_DELETE_WINDOW", lambda: (master.quit(), master.destroy()))

        self.filename = tk.StringVar()
        self.prefix = tk.StringVar()
        self.filter_str = tk.StringVar()

        self.widget_list = []
        self.window_list = []

        self.handle = None
        self.init_loadfile()
        self.init_filter()
        new_frame = tk.Frame(master=self.master)
        self.connection_list = ConnectionList(new_frame)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def init_loadfile(self):
        new_frame = tk.Frame(master=self.master)
        tk.Label(master=new_frame, text='File: ').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.filename).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Button(master=new_frame, text='Select',
                  command=self.load_pcap_file).pack(side=tk.LEFT)
        tk.Button(master=new_frame, text='Export',
                  command=self.export_dialog).pack(side=tk.LEFT)
        new_frame.pack(side=tk.BOTTOM, fill=tk.BOTH)

    def export_dialog(self):
        top = tk.Toplevel(master=self.master)
        top.title("Export figures")
        new_frame = tk.Frame(master=top)
        tk.Label(master=new_frame, text='Name Prefix').pack(side=tk.LEFT)
        tk.Entry(master=new_frame, textvariable=self.prefix).pack(side=tk.LEFT)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)
        new_frame = tk.Frame(master=top)
        tk.Button(master=new_frame, text='Export All',
                  command=self.do_export).pack(side=tk.BOTTOM)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def do_export(self):
        # TODO: export interface:
        # .export(path, prefix)
        pass

    def load_pcap_file(self):
        file_path = askopenfilename(title='Choose .pcap file', initialdir='~/Downloads')
        if file_path:
            try:
                self.filename.set(file_path)
                self.handle = TcpTrace().open(self.filename.get())
                # associate connection list with tcptrace handle
                self.connection_list.associate(self.handle)
            except RuntimeError:
                showerror(title='Open file', message='Unable to load file, check if it is a valid .pcap file')

    def init_filter(self):
        new_frame = tk.Frame(master=self.master)
        tk.Label(master=new_frame, text='Filter: ').pack(side=tk.LEFT)
        filter_entry = tk.Entry(master=new_frame, textvariable=self.filter_str, validate="key")
        vcmd = self.master.register(lambda new_text, entry=filter_entry: self.validate_filter(new_text, entry))
        filter_entry.config(validatecommand=(vcmd, '%P'))
        filter_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Button(master=new_frame, text='Apply', command=self.apply_filter).pack(side=tk.LEFT)
        new_frame.pack(side=tk.TOP, fill=tk.BOTH)

    def validate_filter(self, new_text, filter_entry):
        try:
            # first check if filter expression is valid
            generate_filter(new_text)
            # set color for the status
            filter_entry.config(bg='green')
            return True
        except Exception:
            filter_entry.config(bg='red')
            # always return true
            return True

    def apply_filter(self):
        if not self.handle:
            return
        try:
            self.handle.set_filter(generate_filter(self.filter_str.get()))
            self.connection_list.update()
        except Exception:
            showerror(title='Filter Error', message='Illegal filter expression.')

    def add_widget(self, widget_title, widget_type, *args, **kwargs):
        new_window = tk.Toplevel(master=self.master)
        new_window.title(widget_title)
        widget_obj = widget_type(new_window, *args, **kwargs)
        self.widget_list.append(widget_obj)
        self.window_list.append(new_window)

    # update all widgets with connection list
    def update_widgets(self):
        filter_func = generate_filter(self.filter_str.get()) if self.filter_str.get() else None
        conn_list = self.handle.read(filter_func)
        for widget_obj in self.widget_list:
            widget_obj.update(conn_list)

    def mainloop(self):
        self.master.mainloop()


class ConnectionList:
    # float format
    FLOAT_FMT = '%.3f'

    Headers = [
        ('Packets', lambda x: x['total_packets']),
        ('Bytes', lambda x: x['a2b']['unique_bytes_sent'][0] +
                            x['b2a']['unique_bytes_sent'][0]),
        ('Start Time', lambda x: x['first_packet_time']),
        ('End Time', lambda x: x['last_packet_time']),
        ('Elapsed Time', lambda x: x['elapsed_time']),
    ]

    def __init__(self, master):
        self.sort_status = {}
        self.handle = None
        self.connections = None
        self.listbox = None
        self.master = master
        self.init_treeview()

    def init_treeview(self):
        scrollbar1 = tk.Scrollbar(master=self.master, orient=tk.VERTICAL)
        scrollbar2 = tk.Scrollbar(master=self.master, orient=tk.HORIZONTAL)
        self.listbox = ttk.Treeview(master=self.master,
                                    columns=map(lambda x: x[0], self.Headers),
                                    # show="headings",
                                    yscrollcommand=scrollbar1.set,
                                    xscrollcommand=scrollbar2.set)
        scrollbar1.config(command=self.listbox.yview)
        scrollbar2.config(command=self.listbox.xview)
        scrollbar1.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar2.pack(side=tk.BOTTOM, fill=tk.X)
        self.listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        tk.Button(text='Test me', command=self.get_selected).pack(side=tk.BOTTOM)
        self.init_header()

    def get_selected(self):
        print self.listbox.selection()
        return self.connections, map(lambda iid: map(int, iid.split('-'))
                                     if iid.find('-') != -1 else int(iid),
                                     self.listbox.selection())

    def clear_list(self):
        for iid in self.listbox.get_children():
            self.listbox.delete(iid)

    def init_header(self):
        self.listbox.heading('#0', text='Connections   A <-> B')
        for header, func in self.Headers:
            self.listbox.column(header, width=tkFont.Font().measure(header.title()))
            # here we should save the parameter into default parameter of lambda function
            # or there could raise an error, only the last variable is saved
            self.listbox.heading(header, text=header,
                                 command=lambda f=func, h=header: self.sortby(f, h))

    def sortby(self, func, header):
        if self.handle:
            if header not in self.sort_status:
                self.sort_status[header] = False
            self.update(sorted(self.handle.read(), key=func, reverse=self.sort_status[header]))
            self.sort_status[header] = not self.sort_status[header]

    def associate(self, handle):
        self.handle = handle
        self.update()

    def update(self, conn_list=None):
        # if no connection list is provided, just read from handle
        if conn_list is None:
            if self.handle:
                self.update(self.handle.read())
            return

        # first clear previous data
        self.clear_list()

        # save the connections for selection
        self.connections = conn_list

        def time_wrapper(time_val):
            return self.FLOAT_FMT % time_val

        def get_sub_connection(sub_conn):
            return sub_conn['packets_sent'][0], \
                   sub_conn['unique_bytes_sent'][0], \
                   time_wrapper(sub_conn['first_data_time'][0]), \
                   time_wrapper(sub_conn['last_data_time'][0]), \
                   time_wrapper(sub_conn['data_trans_time'][0])

        for index, conn in enumerate(conn_list):
            conn_details = (conn['total_packets'],
                            conn['a2b']['unique_bytes_sent'][0] + conn['b2a']['unique_bytes_sent'][0],
                            time_wrapper(conn['first_packet_time']),
                            time_wrapper(conn['last_packet_time']),
                            time_wrapper(conn['elapsed_time']))
            a2b_details = get_sub_connection(conn['a2b'])
            b2a_details = get_sub_connection(conn['b2a'])
            conn_str = '%s:%d - %s:%d' % (conn['host_a'], conn['port_a'],
                                          conn['host_b'], conn['port_b'])
            self.listbox.insert('', tk.END, str(index), values=conn_details, text=conn_str)
            self.listbox.insert(str(index), tk.END, str(index) + '-1', text='A to B', values=a2b_details)
            self.listbox.insert(str(index), tk.END, str(index) + '-2', text='B to A', values=b2a_details)

            # adjust tree view width
            col_w = tkFont.Font().measure(conn_str)
            if self.listbox.column('#0', width=None) < col_w:
                self.listbox.column('#0', width=col_w)

            # adjust column width
            for idx in range(len(conn_details)):
                col_w = max(tkFont.Font().measure(str(conn_details[idx])),
                            tkFont.Font().measure(str(a2b_details[idx])),
                            tkFont.Font().measure(str(b2a_details[idx])))
                cur_col = self.listbox.column(self.Headers[idx][0], width=None)
                if cur_col < col_w:
                    self.listbox.column(self.Headers[idx][0], width=col_w+10)
