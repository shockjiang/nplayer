#!/usr/bin/env python
import matplotlib#need to manually install py-matplotlib
matplotlib.use('Agg')
matplotlib.rcParams["font.size"] = 18
matplotlib.rcParams["xtick.labelsize"] = 15
matplotlib.rcParams["ytick.labelsize"] = 15
matplotlib.rcParams["lines.linewidth"] = 3.0
matplotlib.rcParams["pdf.fonttype"] = 42

import os, os.path
import re
import matplotlib.pyplot as plt

class HistoryData(object):
    
    pass

class HistoryList(object):
    def __init__(self, in_dir, **kwargs):
        self.in_dir = in_dir
        self.out_dir = kwargs.get("out_dir", "data/Figure2")
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
            
        self.fs = []
        self.pairs = []
        if not os.path.exists(self.in_dir):
            print "!!!! %s does not exist " %(self.in_dir)
        fnames = os.listdir(self.in_dir)
        
        for f in fnames:
            if self.is_history_file(f):
                self.fs.append(os.path.join(self.in_dir, f))
                
    
    def list_history(self):
        print self.fs
        
    def is_history_file(self, f):
        if os.path.isdir(f):
            return False
        #datassL-2013-11-20 16/15/14.543437.txt
        #re.compile('^datass[L,R]-$')
        if f.startswith("datass") and f.endswith(".txt"):
            return True
        else:
            return False
        
    def draw(self, fL, fR):
        f = open(fL)
        datassL = []
        for line in f.readlines():
            datas = line.split()
            datassL.append(datas)
            
        f = open(fR)
        datassR = []
        for line in f.readlines():
            datas = line.split()
            datassR.append(datas)
        
        
        assert len(datassL) == len(datassR)
        
        for i in range(len(datassL)):
            ll = datassL[i][1:]
            lr = datassR[i][1:]
            name = datassL[i][0]
        
            self.draw_figure(ll, lr, title=name)
            if i == 0:
                break
        
    def draw_figure(self, yl, yr, **kwargs):
        fig = plt.figure()
        ax = fig.add_subplot(111)
        print yl
        ax.grid(True)
        l = ax.plot(range(len(yl)), yl, "g-", label="ACM")
        l = ax.plot(range(len(yr)), yr, "b-", label="Fixed Mode")
        title = kwargs.get("title", None)
        #ax.set_title(title)
        plt.ylabel("Payload Size")
        plt.xlabel("Interest Sent Index")
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        fout = os.path.join(self.out_dir, title+".png")
        plt.savefig(fout)
        print fout
        
            
hl = HistoryList(in_dir="media/Figure")
hl.list_history()
hl.draw(fL="media/Figure/datassL-2013-11-21 101409.041336.txt", fR="media/Figure/datassR-2013-11-21 101409.041336.txt")