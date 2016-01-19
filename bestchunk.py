#! /usr/bin/env python
import matplotlib#need to manually install py-matplotlib
matplotlib.use('Agg')
matplotlib.rcParams["font.size"] = 18
matplotlib.rcParams["xtick.labelsize"] = 18
matplotlib.rcParams["ytick.labelsize"] = 18
matplotlib.rcParams["lines.linewidth"] = 3.0
matplotlib.rcParams["pdf.fonttype"] = 42
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import fsolve
import math
import os, os.path

class PktLoss(object):
    def __init__(self, value_from_test=None, m=None):
        self.value_from_test = value_from_test
        self.m = m
        
        
    def estimate_according_to_two_indexes(self, index_value, chunk_loss_rate, m=None):
        if m == None:
            m = self.m
        
        temp = (m+1.0)/(2*m) *(index_value + chunk_loss_rate)
        #temp = (index_value+chunk_loss_rate)/2.0
        #temp = (m+1)*chunk_loss_rate/(m*2.0) 
        print "when m=%s index_value=%s chunk_loss_rate=%s, Omega=%s" %(m, index_value, chunk_loss_rate, temp)
        if m == 1.0:
            print ""
        return temp
        
    def estimate_according_to_index_value(self, index_value=None, m=None):
        if index_value == None:
            index_value = self.value_from_test
        if m == None:
            m = self.m
        
        temp = 1 - pow(1 - m*index_value, 1.0/m)
        print "when m=%s index_value=%s, Omega=%s" %(m, index_value, temp)
        return temp
    
    def estimate_accordiing_to_chunk_loss_rate(self, chunk_loss_rate, m=None):
        if m == None:
            m = self.m
            
        temp = 1 - pow(1 - chunk_loss_rate, 1.0/m)  
        #print "when chunk_loss_rate=%s, Omega=%s" %(chunk_loss_rate, temp)  
        return temp
    def use_chunk_loss_rate_as_pkt_loss_rate(self, chunk_loss_rate, m=None):
        if m == None:
            m = self.m
        temp = chunk_loss_rate
        
        print "when m=%s chunk_loss_rate=%s, pkt_loss_rate=%s" %(m, chunk_loss_rate, temp)
        
    def get_index_value(self, Omega, m=None):
        if m == None:
            m = self.m
        temp = (1- pow(1-Omega, m))/m
        print "when m=%s, Omega=%s, index_value=%s" %(m, Omega, temp)
        return temp
    
    def analyze(self):
                
        #0.069, 0.565
        
        index_values = [0.0320, 0.0316]
        Omegas = [0.0436, 0.0430]
        
        m = 3.0
        for i in range(len(Omegas)):
            Omega = Omegas[i]
            index_value = index_values[i]
            self.estimate_according_to_index_value(index_value, m)
            print "expection=%s" %(Omega)
            #self.get_index_value(Omega, m)
            #print "expection=%s" %(index_value)
        
pl = PktLoss(value_from_test=0.0, m=3.0)
# pl.analyze()
# pl.estimate_accordiing_to_chunk_loss_rate(chunk_loss_rate=0.03136, m=3.0)


class BestChunk(object):
    def __init__(self, Omega, Delta, M, p=None, h=0.5):
        self.Omega = Omega
        self.Delta = Delta
        self.M = M
        self.p = p
        self.h = h
        self.out_dir = "Figure/"
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
    
    
    def get_payload_size(self, Omega=None, Delta=None):
        if Omega==None:
            Omega = self.Omega
        T = 1 - Omega
        if Delta == None:
            Delta = self.Delta
        M = self.M
        #data size per chunk
        p = (-1*Delta*math.log(T) -pow((Delta*(math.log(T)))**2-4*M*math.log(T)*Delta, 0.5))/(2*math.log(T))
        
        k = int((Delta+p)/float(M))
    
        r1 = self.get_ratio_lower(k*M)
        
        r2 = self.get_ratio_lower((k+1)*M)
        
        
        if r1 > r2:
            p = k*M - Delta
            r = r1
        else:
            p = (k+1)*M - Delta
            r = r2
        
        return p, r
    
    def get_retxN(self, p, Omega):
        if Omega == None:
            Omega = self.Omega
        T = 1 - Omega
        m = math.ceil((Delta+p)/float(M))
        n = pow(float(T), -1*m)
        return n

    
    def get_ratio_upper(self, p, Omega=None, Delta=None):
        if Omega == None:
            Omega = self.Omega
        T = 1 - Omega
        if Delta == None:
            Delta = self.Delta
        
        if type(p) == np.ndarray:
            p = p.astype(np.float)
        else:
            p = float(p)
            
        r = p/(Delta+p)
        
        return r
    
    def get_ratio_reliable(self, p, Omega=None):
        if Omega == None:
            Omega = self.Omega
            
        T = 1 - Omega
        Delta = self.Delta
        M = self.M
        m = (Delta+p)/float(M)

        r = p*T/(Delta+p)
        return r
        
    def get_ratio_lower(self, p, Omega=None, Delta=None):
        if Omega == None:
            Omega = self.Omega
        T = 1 - Omega
        if Delta == None:
            Delta = self.Delta
        M = self.M
        m = np.ceil((Delta+p)/float(M))
        
        r = p*T**(m)/(Delta+p)
        return r
    
    def get_ratio_with_h(self, p, h=None, Omega=None, Delta=None):
        if h == None:
            h = self.h
        if Delta == None:
            Delta = self.Delta
        r1 = self.get_ratio_lower(p, Omega, Delta=Delta)
        r2 = self.get_ratio_upper(p, Omega, Delta=Delta)
        
#         print "h=%s" %(h)
#         print "r1", r1
#         print "r2", r2
        return h*r2 + (1-h)*r1
        
    def f(self, p):
        Omega = self.Omega
        Delta = self.Delta
        M = self.M
        h = self.h
        assert h!=None, "h==None"
        
        m = (Delta+p)/float(M)
        m =  math.ceil((Delta+p)/float(M))
        
        return math.pow(1-Omega, m)*(   Delta + p*m*math.log(1-Omega)  ) + h*Delta/(1-h)

    def get_zero_point(self, h=None):
        if h != None:
            self.h = h
        result = fsolve(self.f, [8832.0])
        #print result
        #print self.f(result)
        #print "ratio=%s" %(self.get_ratio_with_h(p=result[0]))
        return result
#def __init__(self, Omega, Delta, M, p=None, h=0.5):

class RatioGivenPayload(object):
    def __init__(self, Omega):
        self.bc = BestChunk(Omega=Omega, Delta=500, M=1472)
    
    def ratio_given_payload_compare(self, data_size1, data_size2):
        r1 = self.bc.get_ratio_lower(data_size1)
        r2 = self.bc.get_ratio_lower(data_size2)
        
        print "payload=%s, ratio=%s" %(data_size1, r1)
        print "payload=%s, ratio=%s" %(data_size2, r2)
        
rgp = RatioGivenPayload(Omega=0.002)
# rgp.ratio_given_payload_compare(4096, 8350)

class WithH(object):
    def __init__(self, h=0.5, Omega=0.01):
        self.bc = BestChunk(Omega=Omega, Delta=500, M=1472, p=None, h=h)
    
    def ratio_h(self):
        hs = [i*0.01 for i in range(100)]
        ps = []
        rs = []
        crs = []#compare ratios
        cps = []#compare payload sizes
        
        for h in hs:
            p = self.bc.get_zero_point(h=h)[0]
            
            r = self.bc.get_ratio_with_h(p, h=h)
            if h == 0:
                base_r = self.bc.get_ratio_lower(p)
                base_p = p
                
            ps.append(p)
            rs.append(r)
            c = r/float(base_r)
            #print r, base_r
            crs.append(c)
            
            if h<0.9:
                cp = p/float(base_p)
                cps.append(cp)
            
            
            #print "h=%s, p=%6s, r=%6s, cr=%s, cp=%s, base_p=%s, p=%s" %(h, p, r, c, cp, base_p, p)
        
                
        ls = []
        plt.cla()
#         for ys in [rs, crs]:
#             l, = plt.plot(hs, ys)
#             ls.append(l)
#         
        l, = plt.plot(hs, rs)
        ls.append(l)
        
        
        #print ps
        plt.ylim(ymin=0.0, ymax=1.2)
        
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        
        plt.grid(True)
        plt.xlabel("h")
        plt.ylabel("Goodput-To-Throughput Ratio")
        plt.title("UDP: $\Delta$=%s, M=%s, $\Omega$=%s" %(self.bc.Delta, self.bc.M, self.bc.Omega))
        plt.legend([l], ["Max Ratio"], loc="upper left")
        
        
        
        plt.twinx()
        plt.ylim(ymin=0.0, ymax=3.2)
        
        l, = plt.plot(hs, crs, "g")
        ls.append(l)
        
        
        
        l, = plt.plot(hs[0:len(cps)], cps, "r")
        ls.append(l)
        
        
        legends = ["Max Ratio", "Ratio: Max-to-LB", "Payload: Max-to-LB"]
        plt.legend(ls[1:], legends[1:], loc="lower right")
        
        plt.ylabel("Payload Size: Max-to-LowerBound")
        
        name = "ratio-h-M%s-Delta%s-Omega%s" %(self.bc.M, self.bc.Delta, self.bc.Omega)
        name = name.replace(".", "")
        plt.savefig(self.bc.out_dir+"/"+name+".pdf")


        print "%s.pdf ends" %(name)

        
wh = WithH(Omega=0.01)
# wh.ratio_h()
    
class LossComparsion(object):
    def __init__(self):
        self.udp = BestChunk(0.01, 500, 1472)
        
    
    def payload_loss_figure(self):
        ps = []
        rs = []
        rs2 = []
        Omegas = [i*0.001 for i in range(1, 201)]
        last_p = 0 
        for Omega in Omegas:
            self.udp.Omega = Omega
            p, r = self.udp.get_payload_size()
            if p != last_p:
                print "Omega=%s, p=%s, r=%s" %(Omega, p, r)
                last_p = p
            ps.append(p)
            rs.append(r)
            
            r2 = self.udp.get_ratio_lower(p=4096)
            rs2.append(r2/r)
            
        plt.clf()
        plt.cla()
        l, = plt.plot(Omegas, ps)
        plt.legend([l], ["Optimal\nPayload Size"], loc="upper left", prop={'size':18})
        #print ps
        #plt.ylim(ymin=0.0, ymax=1)
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        
        plt.grid(True)
        plt.xlabel("Packet Loss Rate")
        plt.ylabel("Optimal Payload Size per Chunk")
        
        
        
        
        plt.twinx()
#         l1, = plt.plot(Omegas, rs, "g")
#         l2, = plt.plot(Omegas, rs2, "r")
#         plt.ylabel("Max Goodput-to-Throughput Ratio")
#         plt.legend([l1, l2], ["Max G2T Ratio", "Ratio of 4096-to-LB"], loc="upper right",  prop={'size':18})
#         
        l1, = plt.plot(Omegas, rs, "g")
        #l2, = plt.plot(Omegas, rs2, "r")
        plt.ylabel("Max Goodput-to-Throughput Ratio")
        plt.legend([l1], ["Max G2T Ratio"], loc="upper right",  prop={'size':18})
        
        
        plt.title("UDP: $\Delta$=%s, M=%s" %(self.udp.Delta, self.udp.M))
        
        name = "payload-loss-M%s-Delta%s" %(self.udp.M, self.udp.Delta)
        name.replace(".", "")
        plt.savefig(self.udp.out_dir+"/"+name+".pdf")
        
        
        print "%s.pdf ends" %(name)
    
    def ratio_payload_figure(self):
        """there lines, upper bound, lower bound Omega=0.01, lower bound Omega=0.03
        """
        ps = range(1000, 15000, 1)
        rss = []
        peakx = 0
        peaky = 0
        for Omega in [0.01, 0.03]:
            rs = []
            rs2 = []
            rs3 = [] #4096
            for p in ps:
                r = self.udp.get_ratio_lower(p, Omega)
                rs.append(r)
                if r >=peaky:
                        peaky = r
                        peakx = p
                        
                if Omega == 0.01:
                    r = self.udp.get_ratio_upper(p, Omega)
                    rs2.append(r)
                    
                        
            if Omega == 0.01:
                rss.append(rs2)
            rss.append(rs)
        
        ls = []
        plt.cla()
        plt.clf()
        for rs in rss:
            l, = plt.plot(ps, rs)
            ls.append(l)
        
        
        
        plt.ylim(ymin=0.3, ymax=1)
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        plt.title("UDP: $\Delta$=%s, M=%s, $\Omega$=1%%" %(self.udp.Delta, self.udp.M))
        
        plt.fill_between(ps, rss[0], rss[1], color="red", alpha=0.2)
        plt.fill_between(ps, rss[2], rss[1], color="yellow", alpha=0.2)
        
        plt.grid(True)
        plt.ylabel("Goodput-To-Throughput Ratio")
        plt.xlabel("Payload Size per Chunk")
        
        legends = ["Upper Bound", "Lower Bound: $\Omega$=1%", "Lower Bound: $\Omega$=3%"]
        plt.legend(ls, legends, loc="lower right")
        
        plt.plot(peakx, peaky, "yo")
        plt.annotate('Peak Point: (%d, %.3f)' %(peakx, peaky), (peakx, peaky),
            xytext=(0.6, 0.7), textcoords='axes fraction',
            arrowprops=dict(facecolor='black', shrink=0.02),
            fontsize=12,
            horizontalalignment='left', verticalalignment='bottom')
        
        print peakx, peaky
        
        
        name = "ratio-payload-M%s-Delta%s-Omega001003" %(self.udp.M, self.udp.Delta)
        name.replace(".", "")
        plt.savefig(os.path.join(self.udp.out_dir,name+".pdf"))
        
        
        print "%s.pdf ends" %(name)
    
    def ratio_to_4096(self):
        rs = []
        rs2 = []
        rs4 = []
        Omegas = [i*0.001 for i in range(1, 31)]
        last_p = 0 
        for Omega in Omegas:
            self.udp.Omega = Omega
            self.Delta = 438
            p, r = self.udp.get_payload_size(Omega=Omega, Delta=438)
            r2 = self.udp.get_ratio_upper(p=p, Omega=Omega, Delta=438)
            
            r3 = self.udp.get_ratio_lower(p=4096, Omega=Omega, Delta=438) #4096
            r4 = (0.3*r + 0.7*r2)/r3
            rs.append(r/r3)
            rs2.append(r2/r3)
            rs4.append(r4)
            
        plt.cla()
        ls = []
        l, = plt.plot(Omegas, rs)
        ls.append(l)
        l, = plt.plot(Omegas, rs2)
        ls.append(l)
        
        l, = plt.plot(Omegas, rs4)
        ls.append(l)
        plt.legend(ls, ["LB to Base", "UP to Base", "h=0.7 to Base"], loc="upper left", prop={'size':18})
        #print ps
        plt.ylim(ymin=0.0, ymax=2)
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        
        plt.grid(True)
        plt.xlabel("Packet Loss Rate")
        plt.ylabel("Ratio Comparision")
        
        plt.title("UDP: $\Delta$=%s, M=%s" %(self.udp.Delta, self.udp.M))
        
        name = "ratio-to-4096-loss-M%s-Delta%s" %(self.udp.M, self.udp.Delta)
        name.replace(".", "")
        plt.savefig(self.udp.out_dir+"/"+name+".pdf")
        
        
        print "%s.pdf ends" %(name)
    
        

lc = LossComparsion()
lc.payload_loss_figure()       
lc.ratio_payload_figure()
lc.ratio_to_4096()

class ChannelComparision(object):
    def __init__(self):
        self.udp = BestChunk(0.01, 500, 1472)
        #bc2   = BestChunk(0.03, 500, 1472)
        self.ideal = BestChunk(0, 500, 1500)
        self.tcp = BestChunk(0.01, 500, 1460)
#         
#         self.udp.Omega = 0.03
#         self.tcp.Omega = 0.03
    
    def ratio_payload_compare_figure(self):
        """three lines
        """
        ps = range(1000, 15000, 1)
        rss = []
        peakx = 0
        peaky = 0
    
        rs = []
        rs1 = []
        rs2 = []
        for p in ps:
            r = self.ideal.get_ratio_lower(p)#ideal
            rs.append(r)
            
            r = self.tcp.get_ratio_reliable(p)#tcp
            rs1.append(r)
            
            r = self.udp.get_ratio_lower(p)#udp
            rs2.append(r)

        
        rss = [rs, rs1, rs2]
        ls = []
        plt.cla()
        for rs in rss:
            l, = plt.plot(ps, rs)
            ls.append(l)
        
        
        
        plt.ylim(ymin=0.5, ymax=1)
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
            
        plt.fill_between(ps, rss[0], rss[1], color="red", alpha=0.2)
        plt.fill_between(ps, rss[2], rss[1], color="yellow", alpha=0.2)
        
        plt.grid(True)
        plt.ylabel("Goodput-To-Throughput Ratio")
        plt.xlabel("Payload Size per Chunk")
        
        legends = ["Error-Free Channel: M=1.5K", "Reliable Service: TCP", "Best-Efforts Service: UDP"]
        plt.legend(ls, legends, loc="lower right")
        
        plt.title("$\Delta$=%s, $\Omega$=%s" %(self.udp.Delta, self.udp.Omega))
        
        plt.plot(peakx, peaky, "yo")
        plt.annotate('Peak Point: (%d, %.3f)' %(peakx, peaky), (peakx, peaky),
            xytext=(0.6, 0.7), textcoords='axes fraction',
            arrowprops=dict(facecolor='black', shrink=0.02),
            fontsize=12,
            horizontalalignment='left', verticalalignment='bottom')
        
        print peakx, peaky
        
        
        name = "ratio-payload-compare-Delta%s-Omega%s" %(self.udp.Delta, self.udp.Omega)
        name = name.replace(".", "")
        plt.savefig(self.udp.out_dir+"/"+name+".pdf")
        
        
        print "%s.pdf ends" %(name)
        
cc = ChannelComparision()
cc.ratio_payload_compare_figure()

print "end"
