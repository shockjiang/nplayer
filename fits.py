#!/usr/bin/env python

import matplotlib#need to manually install py-matplotlib
matplotlib.use('Agg')
matplotlib.rcParams["font.size"] = 18
matplotlib.rcParams["xtick.labelsize"] = 15
matplotlib.rcParams["ytick.labelsize"] = 15
matplotlib.rcParams["lines.linewidth"] = 3.0
matplotlib.rcParams["pdf.fonttype"] = 42

from matplotlib import cm
import matplotlib.pyplot as plt
#plt.rc('text', usetex=True)
plt.rc('font', family='serif')
import os
import os.path

from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import scipy as sp
import math
from bestchunk import BestChunk
from bestchunk import PktLoss

class Dot(object):
    def __init__(self, index_value, payload, ratio):
        self.index_value = index_value
        self.payload = payload
        self.ratio = ratio
        
        self.ratio_model_lower = None
        self.ratio_model_upper = None
        self.Delta = 438
        self.chunk_loss_rate = None
        self.m = 3.0
        self.bc = BestChunk(Omega=0.01, Delta=438, M=1472)
    def __str__(self):
        #upper = self.bc.get_ratio_upper(p=self.payload, Omega=self.get_pkt_loss_rate(), Delta=self.Delta)
        
        return "lossrate=%s payload=%s ratio=%s ratio_model_lower=%s, ratio_model_upper=%s" \
             %(self.get_pkt_loss_rate(), self.payload, self.ratio, self.ratio_model_lower, self.ratio_model_upper)
    
    def get_pkt_loss_rate(self):
        temp =  self.chunk_loss_rate
        #temp = self.index_value
        return temp

class ErrorBarData(object):
    def __init__(self, m, mode="chunk"):
        self.mode = mode
        self.m = m
        self.dotN = 0
        self.sum = 0
        self.minv = 1
        self.maxv = 0
        self.pkt_loss = PktLoss()
        
    def add_dot_pair(self, dot1, dot2, mode=None):
        assert dot1.m == self.m
        #assert dot2.m == 1.0
        #print dot1.chunk_loss_rate, dot2.chunk_loss_rate
        if mode == None:
            mode = self.mode
            
        if mode == "chunk":
            temp = dot1.chunk_loss_rate/float(dot2.chunk_loss_rate)
        elif mode == "packet":
            temp = self.pkt_loss.estimate_accordiing_to_chunk_loss_rate(chunk_loss_rate=dot1.chunk_loss_rate, m=dot1.m)/float(dot2.chunk_loss_rate)
        elif mode == "ratio":
            temp = dot1.ratio/dot2.ratio     
        elif mode == "bitrate":
            temp = dot1.bitrate/dot2.bitrate
        #print "add temp=%s" %(temp)
        if temp > self.maxv:
            self.maxv = temp
        if temp < self.minv:
            self.minv = temp
            
        self.sum += temp
        self.dotN += 1
        
    def get_data(self):
        if self.dotN == 0:
            return 0, 0, 0
        
        return self.sum/float(self.dotN), self.maxv, self.minv 
        
        

class Fit(object):
    def __init__(self, **kwargs):
        self.fin_path = kwargs.get("fin", "./lossrate-ratio-fits-selection3.txt")
        print self.fin_path, kwargs
        self.dots = []
        self.out_dir = kwargs.get("out_dir", "./data/Figure")
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
            
        self.bc = BestChunk(Omega=0.01, Delta=437, M=1472)
        self.pkt_loss = PktLoss()
        self.dots0 = []
        self.dots1 = []
    
    def ratio_bitrate_m(self, base_size=4096):
        Size = len(self.dots0)
        datas = [ErrorBarData(m=i, mode="ratio") for i in range(7)]
        datas2 = [ErrorBarData(m=i, mode="bitrate") for i in range(7)]
        
        for i in range(Size):
            dot0 = self.dots0[i]
            dot1 = self.dots1[i]
            if dot0.ratio != None and dot1.ratio !=None:
                m = int(dot0.m)
                datas[m].add_dot_pair(dot0, dot1)
                
            if dot0.bitrate != None and dot1.bitrate !=None:
                m = int(dot0.m)
                datas2[m].add_dot_pair(dot0, dot1)
                
        
        bar_width = 0.3
        bar_gap = 0.05
        
        means = [1.01]
        maxs = [0.03]
        mins = [0.02]
        xs = [1-bar_width-bar_gap]
        
        means2 = [1.10]
        maxs2 = [0.1]
        mins2 = [0.07]
        xs2 = [1+bar_gap]
        
        
        for i in range(1, len(datas)):
            xs.append(i- bar_width-bar_gap)
            mean, maxv, minv = datas[i].get_data()
            
            means.append(mean)
            maxs.append(maxv-mean)
            mins.append(mean-minv)
        
            xs2.append(i+bar_gap)    
            mean, maxv, minv = datas2[i].get_data()
            
            means2.append(mean)
            maxs2.append(maxv-mean)
            mins2.append(mean-minv)
        
        fig = plt.figure()
        plt.grid(True)
        ax = fig.add_subplot(111)
        bars = []
        b = ax.bar(xs, means, yerr=[mins, maxs], color='y', width=bar_width, align='edge')
        bars.append(b)
        
        b = ax.bar(xs2, means2, yerr=[mins2, maxs2], color='b', width=bar_width, align='edge')
        bars.append(b)
        
        #ax.errorbar(xs, means, yerr=[mins, maxs])
        plt.xlabel("payload size (measured by # of packet)")
        plt.ylabel("G2T Ratio/ Bit rate")
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        plt.ylim(ymax=2.0)
        
        plt.legend(bars, ["G2T Ratio", "Bit Rate"])
        fout = self.out_dir+"/ratioandbitrate-m-%s.png" %(base_size)
        plt.savefig(fout)
        print fout
        
            
        
    def estimate_pkt_loss_rate(self, base_size=1030):

#             
        fig = plt.figure()
        plt.grid(True)
        ax = fig.add_subplot(111)
        #ax = fig.add_subplot(111, projection="3d")
        xs = []
        dots1 = self.dots0
        dots2 = self.dots1
        ys1 = []
        ys2 = []
#         for i in range(len(self.dots)):
#             dot = self.dots[i]
#             if i % 2 == 0:
#                 dots1.append(dot)
#             else:
#                 dots2.append(dot)
#                 
        datas = [ErrorBarData(m=i, mode="chunk") for i in range(7)]
        datas2 = [ErrorBarData(m=i, mode="packet") for i in range(7)]
        for i in range(len(dots1)):
            dot1 = dots1[i]
            dot2 = dots2[i]
            #assert dot1.m == dot2.m, "dot1=%s, dot2=%s" %(dot1, dot2)
            
            datas[int(dot1.m)].add_dot_pair(dot1, dot2)
            datas2[int(dot1.m)].add_dot_pair(dot1, dot2)
            #print dot1.m
        
        means = []
        maxs = []
        mins = []
        xs = []
        
        means2 = []
        maxs2 = []
        mins2 = []
        xs2 = []
        bar_width = 0.3
        bar_gap = 0.05
        for i in range(1, len(datas)):
            xs.append(i- bar_width-bar_gap)
            mean, maxv, minv = datas[i].get_data()
            
            means.append(mean)
            maxs.append(maxv-mean)
            mins.append(mean-minv)
        
            xs2.append(i+bar_gap)    
            mean, maxv, minv = datas2[i].get_data()
            
            means2.append(mean)
            maxs2.append(maxv-mean)
            mins2.append(mean-minv)
            
        bars = []
        b = ax.bar(xs, means, yerr=[mins, maxs], color='y', width=bar_width, align='edge')
        bars.append(b)
        
        b = ax.bar(xs2, means2, yerr=[mins2, maxs2], color='b', width=bar_width, align='edge')
        bars.append(b)
        
        #ax.errorbar(xs, means, yerr=[mins, maxs])
        plt.xlabel("payload size (measured by # of packet)")
        plt.ylabel("Estimated Loss Rate/Packet Loss Rate")
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        plt.ylim(ymax=2.0)
        
        plt.legend(bars, ["$\Omega_{measured1}$", "$\Omega_{measured2}$"])
        fout = self.out_dir+"/loss-rate-fits-%s.png" %(base_size)
        plt.savefig(fout)
        print fout
        
    
    def residuals_h(self, h,  y, x):
        #lossrate, payload, Delta= x
        lowerv, upperv = x
        #print x
        y0 = (1.0-h)*lowerv + h *upperv
        #y0 = self.bc.get_ratio_with_h(p=payload, h=h, Omega=lossrate, Delta=Delta)
        #print "y0", y0
        err =  y - y0
        #print err*100
        #print "err", err
        return err
    
    def residuals_h2(self, x, h):
        lossrate, payload, Delta= x
        
        y0 = self.bc.get_ratio_with_h(p=payload, h=h, Omega=lossrate, Delta=Delta)
        #print h, y0
        return y0
    
    def leastsq_h(self):
        print "least fit------"
        #lossrate, payload, Delta= x
        ratios = []
        ratios_model_upper = []
        ratios_model_lower = []
        
        for dot in self.dots0:
            ratios_model_lower.append(dot.ratio_model_lower)
            ratios_model_upper.append(dot.ratio_model_upper)
            ratios.append(dot.ratio)
            assert ratios_model_lower[-1] != ratios_model_upper[-1]
            #print dot
            
        
        y = np.array(ratios)
        x = [np.array(ratios_model_lower), np.array(ratios_model_upper)]
#         print y
#         print x[0]
#         print x[1]
        h0 = 0.4
        hlsq = sp.optimize.leastsq(self.residuals_h, h0, args=(y, x))
        print hlsq[0], hlsq
    
    def curve_fit_h(self):
        print "curve fit-------"
        lossrates = []
        payloads = []
        Deltas = []
        
        ratios = []
        for dot in self.dots:
            lossrates.append(dot.get_pkt_loss_rate())
            payloads.append(dot.payload)
            Deltas.append(dot.Delta)
            ratios.append(dot.ratio)
        
        
        y = np.array(ratios)
        x = [np.array(lossrates), np.array(payloads), np.array(Deltas)]
        print sp.optimize.curve_fit(self.residuals_h2, x, y)
        
    def load_data(self, fin_path=None, **kwargs):
        if fin_path == None:
            fin_path = self.fin_path
        
        base_chunk_data_size = kwargs.get("base_size", 4096)
        print kwargs, base_chunk_data_size
        
        fin = open(self.fin_path)
        i = 0
        for line in fin.readlines():
            line = line.strip()
            
            if line == "":
                continue
            if line.startswith("#"):
                #print line
                continue
            
            parts = line.split()
            
            assert len(parts) >= 3, "parts do not follow the schema: %s"%(parts)
            if len(parts) < 7:
                #continue
                pass
            
            index_value = float(parts[0].split("=")[1]) * 1.2
            payload = float(parts[1].split("=")[1])
            chunk_header_size = int(parts[6].split("=")[1]) if len(parts) > 7 else 438
            Delta = chunk_header_size
            temp = (payload+Delta)/1472.0
            if temp - int(temp) < 0.1:
                temp = int(temp)
            else:
                temp = int(temp) + 1
            m = temp
            ratio = float(parts[2].split("=")[1])
            bitrate = float(parts[5].split("=")[1]) if len(parts) > 5 else None
            chunk_loss_rate = float(parts[7].split("=")[1]) if len(parts) > 7 else index_value *m
            
            
            dot = Dot(index_value, payload, ratio)
            
            dot.Delta = Delta
            dot.m = m
            dot.chunk_loss_rate = chunk_loss_rate
            dot.bitrate = bitrate
            
            
            ratio_model_lower = self.bc.get_ratio_lower(p=payload, Omega=dot.get_pkt_loss_rate(), Delta=Delta)
            #ratio_model_lower = self.bc.get_ratio_lower(p=payload, Omega=chunk_loss_rate, Delta=Delta)
            if ratio < ratio_model_lower and payload > 1500:
                print "ratio<ratio_model_lower:%s" %(line)
            
#             ratio_model_lower = self.bc.get_ratio_lower(p=payload, Omega=index_value, Delta=Delta)
#             if ratio > ratio_model_lower:
#                 print "2ratio<ratio_model_lower:%s" %(line)
            dot.ratio_model_lower = ratio_model_lower  
            
            ratio_model_upper = self.bc.get_ratio_upper(p=payload, Omega=dot.get_pkt_loss_rate(), Delta=Delta)
            #ratio_model_lower = self.bc.get_ratio_lower(p=payload, Omega=chunk_loss_rate, Delta=Delta)
            if ratio > ratio_model_upper:
                print "ratio>ratio_model_upper:%s" %(line)
            
#             ratio_model_lower = self.bc.get_ratio_lower(p=payload, Omega=index_value, Delta=Delta)
#             if ratio > ratio_model_lower:
#                 print "2ratio<ratio_model_lower:%s" %(line)
            dot.ratio_model_upper = ratio_model_upper  
            
            
            self.dots.append(dot)
            
            if i % 2 == 0:
                self.dots0.append(dot)
                #print "dot=%s" %(dot)
            else:
                self.dots1.append(dot)
                if base_chunk_data_size != None:
                    assert dot.payload == base_chunk_data_size, "%s" %(line)
                
            
            i += 1
    
    def draw2(self, base_size=4096):
        ls = np.arange(0, 0.30, 0.005)
        ps = np.arange(1000, 9000, 10)
        
        ls, ps = np.meshgrid(ls, ps)
        rs = self.bc.get_ratio_lower(ps, ls, Delta=438)
        dot = self.dots0[0]
        r = self.bc.get_ratio_lower(dot.payload, dot.get_pkt_loss_rate(), Delta=dot.Delta)
        #print dot.Delta
        assert r == dot.ratio_model_lower
        
        fig = plt.figure()
        plt.grid(True)
        ax = fig.add_subplot(111, projection="3d")
        ax.plot_surface(ls, ps, rs, rstride=1, cstride=1, color="y",                       
                        linewidth=0, antialiased=True) #cmap=cm.coolwarm, \
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        plt.ticklabel_format(style='sci', axis='z', scilimits=(-2,-1))
        #plt.savefig("test2.png")
        
        self.draw(ax=ax, base_size=base_size)
        
    
    def draw(self, ax=None,base_size=4096):
        xs = []
        ys = []
        zs = []
        z2s = []    
        for dot in self.dots:
            xs.append(dot.get_pkt_loss_rate())
            ys.append(dot.payload)
            zs.append(dot.ratio_model_lower)
            z2s.append(dot.ratio)
            if dot.payload > 1500:
                assert dot.ratio > dot.ratio_model_lower
            #print dot
        if ax == None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")
            fout = "loss-payload-ratio-%s.png" %(base_size)
            
        else:
            fout = "loss-payload-ratio-overlap-%s.png" %(base_size)
        fout = os.path.join(self.out_dir, fout)
        #ax.plot(xs, ys, zs)
        ax.scatter(xs, ys, zs, s=15, c='b', marker="^")#by model, should be a little small
        ax.scatter(xs, ys, z2s, s=15, c='r') #experiment, should be a little large
        
        ax.set_xlim(0, 0.30)#loss rate
        ax.set_ylim(0, 9000) #payload
        ax.set_zlim(0, 1) #ratio
        
        
        plt.xlabel("Pkt Loss Rate")
        plt.ylabel("Payload")
        ax.set_zlabel("G2T Ratio")
        
        
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        plt.show()
        plt.savefig(fout)
        
        print "save fig to %s" %(fout)
    
    def show_bit_rate(self, **kwargs):
        
        xs = []
        ys = []
        
        xs2 = [] #chunksize
        ys3 = [] #bit rate
        xs3 = [] #chunksize but corresponding to ys3
        Dot_Size = len(self.dots0)
        base_size = kwargs.get("base_size", 4096)
        
        for i in range(Dot_Size):
            dot0 = self.dots0[i] #optimal
            dot1 = self.dots1[i] #fixed
            if base_size != None:
                assert dot1.payload == base_size
            xs.append(dot1.get_pkt_loss_rate())
            xs2.append(dot0.payload)
            
            temp = dot0.ratio/dot1.ratio
            if temp < 0.95:
                print temp, dot0
            ys.append(temp)
            
            
            if dot0.bitrate != None and dot1.bitrate != None:
                xs3.append(dot0.payload)
                temp = dot0.bitrate/dot1.bitrate
                if temp < 0.8:
                    print temp, dot0
                ys3.append(temp)
            
        print xs
        print ys
        fig = plt.figure()
        plt.grid(True)
        ax = fig.add_subplot(111)
        ax.plot(xs, ys, "o")
        plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        plt.xlabel("Packet Loss Rate")
        plt.ylabel("G2T Ratio")
        #ax.set_ylim(0, 9000)
        #ax.set_xlim(0, 0.2)
        
        fout = os.path.join(self.out_dir, "ratio-lossrate-benchmark-cmp-%s.png" %(base_size))
        plt.savefig(fout)
        print "save fig to %s" %(fout)
        
        
#         fig = plt.figure()
#         plt.grid(True)
#         ax = fig.add_subplot(111)
#         ax.plot(xs2, ys, "o")
#         plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
#         plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
#         #ax.set_ylim(0, 9000)
#         #ax.set_xlim(0, 0.2)
#         
#         fout = os.path.join(self.out_dir, "ratio-chunksize-benchmark-cmp-%s.png" %(base_size))
#         plt.savefig(fout)
#         print "save fig to %s" %(fout)
#         
#         
#         fig = plt.figure()
#         plt.grid(True)
#         ax = fig.add_subplot(111)
#         ax.plot(xs3, ys3, "o")
#         plt.ticklabel_format(style='sci', axis='x', scilimits=(0,1))
#         plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
#         #ax.set_ylim(0, 9000)
#         #ax.set_xlim(0, 0.2)
#         
#         fout = os.path.join(self.out_dir, "bitrate-chunksize-benchmark-cmp-%s.png" %(base_size))
#         plt.savefig(fout)
#         print "save fig to %s" %(fout)
        
            
fit = Fit()
fit.load_data(base_size=1030)
# fit.draw2(base_size=1030) #loss-payload-ratio-overlap.png
# fit.draw(ax=None, base_size=1030) #loss-payload-ratio
# fit.leastsq_h()
# fit.curve_fit_h()
# fit.show_bit_rate(base_size=1030) #bitrate-fits.png
fit.estimate_pkt_loss_rate(base_size=1030)#lossrate-m-fit.png"

kwargs={"fin":"./lossrate-ratio-fits-selection.txt"}
fit = Fit(**kwargs)
fit.load_data(base_size=4096)
# fit.leastsq_h()
# fit.curve_fit_h()

fit.draw2(base_size=4096) #loss-payload-ratio-overlap.png
#    fit.draw(ax=None, base_size=4096) #loss-payload-ratio
#fit.estimate_pkt_loss_rate(base_size=4096)#lossrate-m-fit.png"
fit.show_bit_rate(base_size=4096)
#fit.ratio_bitrate_m(base_size=4096)
