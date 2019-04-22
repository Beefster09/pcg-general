import tkinter as tk
import tkinter.ttk as ttk
import ruins
import subprocess


class Log(tk.Frame):
    def __init__(self, root, file='ruins_log.txt'):
        super(Log, self).__init__(root)
        self.file = file
        self.main = tk.Text(self, wrap=tk.NONE)
        self.main.grid(row=0, column=0)
        yscroll = ttk.Scrollbar(self, command=self.main.yview)
        yscroll.grid(row=0, column=1, sticky='nsw')
        xscroll = ttk.Scrollbar(self, command=self.main.xview, orient=tk.HORIZONTAL)
        xscroll.grid(row=1, column=0, sticky='new')
        self.main['yscrollcommand'] = yscroll.set
        self.main['xscrollcommand'] = xscroll.set
        self.main.bind('<Key>', self.keypress)

    def keypress(self, event):
        if event.state == 0x4 and event.keysym == 'c':
            return  #Allow CTRL + C
        else:
            return 'break'  #disallow all other typing

    def update_text(self):
        file = open(self.file)
        text = file.read()
        file.close()
        self.main.delete(1.0, tk.END)
        self.main.insert(tk.END, text)


class Options(tk.Frame):
    def __init__(self, root, log):
        super(Options, self).__init__(root)
        self.log = log
        str_opts = ('tablefmt', 'bot-dir',
                    'replay', 'seed')
        self.options = {i: tk.StringVar() for i in str_opts}
        self.log_types = {i: tk.BooleanVar() for i in ruins.MSG_TYPES}
        for i in self.log_types:
            self.log_types[i].set(True)
        tk.Label(self, text='Options').grid(row=0, column=0, columnspan=2)
        self.single = tk.BooleanVar()
        self.scrape = tk.BooleanVar()
        ltframe = tk.Frame(self)
        ltframe.grid(row=1, column=0, columnspan=2)
        r = 0
        c = 0
        for i in ruins.MSG_TYPES:
            ttk.Checkbutton(ltframe, text=i,
                            variable=self.log_types[i]).grid(row=r, column=c, sticky='w')
            r += 1
            if r == 5:
                r = 0
                c += 1
        r = 2
        for i in self.options:
            tk.Label(self, text=i).grid(row=r, column=0, sticky='e')
            ttk.Entry(self, textvariable=self.options[i]).grid(row=r, column=1, pady=1)
            r += 1
        ttk.Checkbutton(self, text='single', variable=self.single)\
                              .grid(row=r, column=0)
        ttk.Checkbutton(self, text='scrape', variable=self.scrape)\
                              .grid(row=r, column=1)
        ttk.Button(self, text='Run', command=self.run).grid(row=r+1, column=0, columnspan=2)

    def run(self):
        commands = ['ruins.py']
        for i in self.options:
            if self.options[i].get():
                commands.append('--' + i)
                commands.append(self.options[i].get())
        if self.single.get():
            commands.append('--single')
        if self.scrape.get():
            commands.append('--url')
            commands.append('https://codegolf.stackexchange.com/questions/183101/adventurers-in-the-ruins')
        commands.append('--only')
        commands += [i for i in self.log_types if self.log_types[i].get()]
        logfile = open('ruins_log.txt', 'w')
        subprocess.run(commands, stdout=logfile, stderr=logfile, shell=True)
        logfile.close()
        self.log.update_text()
        

root = tk.Tk()
root.title('Adventures In The Ruins')
log = Log(root)
log.grid(row=0, column=0)
Options(root, log).grid(row=0, column=1)
tk.mainloop()
        
