#!/usr/bin/env python
# Copyright (c) 2013, Tsinghua University, P.R.China 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the ndn_name of the Tsinghua University nor
#       the names of its contributors may be used to endorse or promote
#       products derived from this software without specific prior written
#       permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL REGENTS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Written by:
#            Zhaogeng Li <lizhaogeng1989@gmail.com>
#            Ao Guo <guoaobupt@gmail.com>
#            Xiaoke Jiang <shock.jiang@gmail.com>

#To do
#1) data visualization



import pygtk
import gtk
pygtk.require('2.0')
gtk.gdk.threads_init()

import logging
import os
import sys
import os.path
import argparse
import random
import datetime
import thread
import threading
import time
import platform
from nplayer import Player
from nplayer import log

import matplotlib#need to manually install py-matplotlib
matplotlib.use('Agg')
matplotlib.rcParams["font.size"] = 18
matplotlib.rcParams["xtick.labelsize"] = 18
matplotlib.rcParams["ytick.labelsize"] = 18
matplotlib.rcParams["lines.linewidth"] = 3.0
matplotlib.rcParams["pdf.fonttype"] = 42
import matplotlib.pyplot as plt


PRODUCER = "vt"
PRODUCER = "seu" 
#PRODUCER = "h243"
#PRODUCER = "super"
PRODUCER = "local"
 
#DATA_FILE = "c"
#DATA_FILE = "d" #100M
DATA_FILE = "e" #50M
#DATA_FILE = "f" #30M
#DATA_FILE = "m" #10M, real mp4 file
DATA_FILE = "b" #6M, real mp4 file

#DATA_FILE = "g" #400K


VIDEO_WIDTH = 400
VIDEO_HEIGHT = 250
SAMPLE_FREQ = 1/1.0

FIGURE_WIDTH = 200
FIGURE_HEIGHT = 150
#FIGURE_WIDTH = 300
#FIGURE_HEIGHT = 200



#from nplayer import Player, log
#gst.element_factory_make("appsrc", "Source")
# class Player(object):
#     def __init__(self, gui):
#         pass
#     
#     def start(self):
#         print "start"
#         
#     def start_stop(self, label, value):
#         print "start-stop"
#     
#     
#     
    
class Gui(object):
    def __init__(self, args, **kwargs):
        self.out_dir = "media/Figure"
        if self.out_dir.endswith("/"):
            self.out_dir = self.out_dir[:-1]
            
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
        self.out_extension = "png"
        
        self.show_movie = args.show_movie
        self.show_figure = args.show_figure
        #self.show_gui = args.show_gui
        
        
        
        w = 30
        h = 100
        if self.show_movie:
            wmovie = 2*VIDEO_WIDTH+30
            w = wmovie if wmovie > w else w
            h += VIDEO_HEIGHT
        
        if self.show_figure:
            wfigure = 4 * FIGURE_WIDTH + 40
            w = wfigure if wfigure > w else w
            h += 2 * FIGURE_HEIGHT
        
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_position(gtk.WIN_POS_CENTER)
        window.set_title("nplayer: A NDN Based Media Player")
        
    
    
        window.set_default_size(w, h)
    
        
        
        window.connect("destroy", gtk.main_quit, "WM destroy")
        vbox = gtk.VBox() #whole frame
        window.add(vbox)
        
        hbox = gtk.HBox() #label entry
        hbox0 = gtk.HBox() #movie frame
        hbox0.set_size_request(2*VIDEO_WIDTH,VIDEO_HEIGHT)
        hbox1 = gtk.HBox(False, 2) #left mute button
        hbox2 = gtk.HBox() #right mute button
        hbox3 = gtk.HBox() #mute button frame to include left and right one
        
        vbox.pack_start(hbox, False)
        vbox.pack_start(hbox3, False)
        
        if self.show_movie:
            vbox.pack_start(hbox0, False)
        
        self.entryL = gtk.Entry()
        self.entryL.set_text("/"+PRODUCER+"/chunksize/dir/%s1.mp4" %(DATA_FILE))    
        hbox.add(self.entryL)
        
        self.button = gtk.Button("Start")
        hbox.pack_start(self.button, False)
        self.button.connect("clicked", self.start_stop)
        
        
        self.entryR = gtk.Entry()
        self.entryR.set_text("/"+PRODUCER+"/chunksize/dir/%s2.mp4" %(DATA_FILE))
        hbox.add(self.entryR)
        
        
        hbox3.pack_start(hbox1,False)
        hbox3.pack_end(hbox2,False)
        self.mur = gtk.Button("muteR")
        
        
        self.mul = gtk.Button("muteL")
        
        
        self.mul.connect("clicked", self.mute)
        self.mur.connect("clicked", self.mute)
        
        
        
        hbox1.add(self.mul)
        #text = gtk.TextView(gtk.GtkTextBuffer("Adaptive Chunk Size"))
        label = gtk.Label()#"                    Interest.LifeTime=RTO")
        gtk.Label.set_markup(label, "<span foreground=\"#0000FF\" size=\"large\" weight=\"bold\">     Stream Left (Blue Line)   </span>")
        #gtk.Label.set_markup(label, "<span foreground=\"#FF0000\">                                                                           Without Stream Fetch Layer (Window Size = 1500, RTO = 4s)    </span>")
        #gtk.Label.set_markup(label, "<span foreground=\"#FF0000\">                                                             With Stream Fetch Layer (Maximum Window Size = 1500, Maximum RTO = 4s)    </span>")

        hbox1.add(label)
        

        label = gtk.Label()#"Fixed Chunk Size: 4096                    ")
        gtk.Label.set_markup(label, "<span foreground=\"#9ACD32\" size=\"large\" weight=\"bold\">     Stream Right (Green Line)       </span>")
        hbox2.add(label)
        hbox2.add(self.mur)
        
        self.movieL = gtk.DrawingArea()
            #self.movieL.set_size_request(VIDEO_WIDTH,VIDEO_HEIGHT)
        self.movieR = gtk.DrawingArea()
        #self.movieR.set_size_request(VIDEO_WIDTH,VIDEO_HEIGHT)
        
        if self.show_movie:            
            hbox0.add(self.movieL)
            hbox0.add(self.movieR)
        
            
        
        self.figure1 = gtk.Image() 
        self.figure2 = gtk.Image() 
        self.figure3 = gtk.Image() 
        self.figure4 = gtk.Image() 
        self.figure5 = gtk.Image()
        self.figure6 = gtk.Image()
        self.figure7 = gtk.Image()
        self.figure8 = gtk.Image()
        
        hbox_f1 = gtk.HBox()
        hbox_f1.pack_start(self.figure2)
        hbox_f1.pack_start(self.figure5)
        hbox_f1.pack_start(self.figure6)
        hbox_f1.pack_start(self.figure7)
        
        hbox_f2 = gtk.HBox()
        hbox_f2.pack_start(self.figure3)
        hbox_f2.pack_start(self.figure4)
        hbox_f2.pack_start(self.figure1)
        hbox_f2.pack_start(self.figure8)
        if self.show_figure:
            vbox.pack_start(hbox_f1)
            vbox.pack_start(hbox_f2)
            
        self.figures_is_ready = False
        
        
        self.playerL = Player(gui=self, name="L")#gui should be passed, therefore, player notify the events from bottom. (with gui.on_message)
        self.playerR = Player(gui=self, name="R")
        
        self.first_run = True
        self.is_sample = False
        
        window.show_all()
        
    
    def on_message(self, message):
        """response to the call from lower layer (player), 
        for example, player reaches the end of the stream (eos), this should be showed by gui
        """
        print message
        if message == "end-of-stream":
            if self.playerL.is_end and self.playerR.is_end:
                self.button.set_label("Start")
            
        elif message == "end-of-data-requesting":
            #not implemented yet
            if not self.show_gui:
                self.stop()
            pass
            
    def start_stop(self, w): 
        if self.first_run:
            self.playerL.start()
            self.playerR.start()
            
            self.is_sample = True
            
            
        cmd_label = self.button.get_label()
            
        filepathL = self.entryL.get_text()
        self.playerL.start_stop(cmd_label, filepathL)
        
        filepathR = self.entryR.get_text()
        self.playerR.start_stop(cmd_label, filepathR)
        
        if self.button.get_label() == "Start":
            self.button.set_label("Stop")
        else:
            self.button.set_label("Start")
        
        if self.first_run:
            thread.start_new_thread(self.sample, ())
            self.first_run = False
            
    def mute(self, w):
        label = w.get_label()
        Id = label[-1:]
        
        value = True
        if label.startswith("mute"):
            value = True
            newlb = "unmute"
        else:
            value = False
            newlb = "mute"
        
        
        print value, label, Id
        if Id == "L":
            self.playerL.mute(value)
            
        else:
            self.playerR.mute(value)
            
        
        w.set_label(newlb+Id)
    
    
    def sample(self):
        while self.is_sample or self.first_run:
            
            #print "---sample----, is_sample=%s, first_run=%s" %(self.is_sample, self.first_run)
            #print "L: is_end=%s, R: is_end=%s" %(self.playerL.ndnsrc.is_end, self.playerR.ndnsrc.is_end)
            
            #log.debug("sample")
            #sample from the left player
            #OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rtos, BitRates, Goodputs = self.playerL.sample()

            
            #keep in mind that all the value could be None 
            
            #sample for the right player
            pL = self.playerL.sample() #performance of L player
            pR = self.playerR.sample() #performance of R player
            
            #print pL
            #self.update_performance_figures(pL, pR)
            self.update_figures(pL, pR)
            time.sleep(int(1/SAMPLE_FREQ))
            self.load_figures()
            if self.playerL.ndnsrc.is_end and self.playerR.ndnsrc.is_end:
                self.is_sample = False
                break
        
        for i in [1, 2]:
            pL = self.playerL.sample() #performance of L player
            pR = self.playerR.sample() #performance of R player
            
            #print pL
            #self.update_performance_figures(pL, pR)
            self.update_figures(pL, pR)
            time.sleep(int(1/SAMPLE_FREQ))
            self.load_figures()
        
        trial_id = str(datetime.datetime.now()).replace(":", "")
        bitrate1 = self.playerL.ndnsrc.flow.mydata.accept_bytes/self.playerL.ndnsrc.flow.mydata.get_time_cost()
        bitrate2 = self.playerR.ndnsrc.flow.mydata.accept_bytes/self.playerR.ndnsrc.flow.mydata.get_time_cost()
        bitrates = [bitrate1, bitrate2]
        
#         i = 0
#         for lis in [pL, pR]:
#             lossrate = lis[1][-1]
#             goodput = lis[5][-1]
#             throughput = lis[7][-1]
#             payload = lis[0][-1]
#             bitrate = bitrates[i]
#             
#             if i == 0:
#                 flow = self.playerL.ndnsrc.flow
#             else:
#                 flow = self.playerR.ndnsrc.flow
#                 
#             header_size = flow.chunk_header_size
#             lossrate2 = flow.chunkSizeEstimator.get_loss_rate2()
#             
#             waiting_time = flow.mydata.get_time_cost()
#             
#             print "lossrate=%s\tpayload=%s\tratio=%s\ttrialid=%s\tbitrate=%s\theadersize=%s\tlossrate2=%swaitingtime=%s" %(
#                         lossrate, payload, goodput/float(throughput), trial_id, bitrate, header_size, lossrate2, waiting_time)
#             i += 1
#         
        self.summary(pL, self.playerL.ndnsrc.flow, bitrate=bitrate1, trialid=trial_id)
        self.summary(pR, self.playerR.ndnsrc.flow, bitrate=bitrate2, trialid=trial_id)
        
        tags = ["chunksize", "lossrate", "windowsize", "rto", "bitrate", "goodput", "throughput", "requestedsize"]
        outpath= "%s/datassL-%s.txt" %(self.out_dir, trial_id)
        lis = pL
        self.save_datass(outpath, lis, tags)
        
        outpath= "%s/datassR-%s.txt" %(self.out_dir, trial_id)
        lis = pR
        self.save_datass(outpath, lis, tags)
        
        
        
        print "reach end of data requesting, not any more"
        
        if not self.show_gui:
            self.stop()
        
    def summary(self, playerinfos, flow, **kwargs):
        lis = playerinfos
        lossrate = lis[1][-1]
        goodput = lis[5][-1]
        throughput = lis[7][-1]
        payload = lis[0][-1]
        bitrate = kwargs.get("bitrate", None)
        trial_id = kwargs.get("trialid", None)
        fout = kwargs.get("fout", "data/gui-summary.txt")
        
        header_size = flow.chunk_header_size
        lossrate2 = flow.chunkSizeEstimator.get_loss_rate2()
        
        flowdata = str(flow.mydata)
        msg =  "lossrate=%s payload=%s ratio=%s trialid=%s bitrate=%s headersize=%s lossrate2=%s %s" %(
                    lossrate, payload, goodput/float(throughput), trial_id, bitrate, header_size, lossrate2, flowdata)
        
        if fout != None:
            if type(fout) == str:
                fout = open(fout, "a")
                fout.write(msg)
                fout.flush()
                fout.close()
            elif type(fout) == file:
                fout.write(msg)
        else:
            pass
        
        print msg
    
    def update_figures(self, pL, pR):
        if pL[0] == None or pR[0] == None:
            return
        
        len_size = len(pL)
        for i in range(len_size):
            datas = [pL[i], pR[i]]
            if i == 0:
                title = "Optimal Chunk Sizes"
                outname = "chunksize"
                xlabel = "Interest Index"
                ylabel = None
            elif i == 1:
                title = "Packet Loss Rate"
                outname = "lossrate"
                xlabel = "Interest Index"
                ylabel = None
            elif i == 2:
                title = "Congestion Window Size"
                outname = "windowsize"
                xlabel = "Interest Index"
                ylabel = None
            elif i == 3:
                title = "RTO or Lifetime"
                outname = "rto"
                xlabel = "Interest Index"
                ylabel = None
            elif i == 4:
                title = "Bit Rate"
                outname = "bitrate"
                xlabel = "Time x%ss" %(1.0/SAMPLE_FREQ)
                ylabel = None
            elif i == 5:
                title = "Goodput"
                outname = "goodput"
                xlabel = "Time x%ss" %(1.0/SAMPLE_FREQ)
                ylabel = None
            elif i == 6:
                title = "Throughput"
                outname = "througput"
                xlabel = "Time x%ss" %(1.0/SAMPLE_FREQ)
                ylabel = None
                #print i, datas
            elif i == 7:
                title = "Requested Size"
                outname = "requestedsize"
                xlabel = "Time x%ss" %(1.0/SAMPLE_FREQ)
                ylabel = None
                #print i,  datas
            else:
                print "no i=%s" %(i)
            
            self.draw_figure(outname, title, xlabel, ylabel, datas)
            
        self.figures_is_ready = True
    
    def draw_figure(self, outname, title, xlabel, ylabel, datas, **kwargs):
        plt.cla()
        ls = []
#         for data in datas:
#             l, = plt.plot(data)
#             ls.append(l)
#         
        l, = plt.plot(datas[0], "b-")
        ls.append(l)
        
        l, = plt.plot(datas[1], "g-")
        ls.append(l)
        #plt.legend([l], ["Optimal\nPayload Size"], loc="upper left", prop={'size':18})
        #print ps
        #plt.ylim(ymin=0.0, ymax=1)
        plt.ticklabel_format(style='sci', axis='x', scilimits=(3,3))
        plt.ticklabel_format(style='sci', axis='y', scilimits=(-2,0))
        
        
        plt.grid(True)
        plt.xlabel(xlabel)
        if ylabel != None:
            plt.ylabel(ylabel)
        
        
        plt.title(title)
        
        outpath = "%s/%s.png" %(self.out_dir, outname)
        plt.savefig(outpath)
        
        if self.out_extension != "png":
            outpath = "%s/%s.%s" %(self.out_dir, outname, self.out_extension)
            plt.savefig(outpath)
        
    def save_datass(self, outpath, lis, tags):
        fout = open(outpath, "w")
        assert len(lis) == len(tags), "len(lis)=%s, len(tags)=%s, tags=%s" %(len(lis), len(tags), tags)
        
        
        for i in range(len(lis)):
            tag = tags[i]
            li = lis[i]
            fout.write("%s" %(tag))
            for val in li:
                fout.write("\t%s" %(val))
            fout.write("\n")
        
            
        fout.close()
    
    def load_figures(self):
        if not os.path.exists('%s/chunksize.%s' %(self.out_dir, self.out_extension)):
            return
        if not self.figures_is_ready:
            return
        
        pixbuf1 = gtk.gdk.pixbuf_new_from_file('%s/chunksize.%s' %(self.out_dir, self.out_extension))
        pixbuf1 = pixbuf1.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure1.set_from_pixbuf(pixbuf1)
        pixbuf2 = gtk.gdk.pixbuf_new_from_file('%s/lossrate.%s' %(self.out_dir, self.out_extension))
        pixbuf2 = pixbuf2.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure2.set_from_pixbuf(pixbuf2)
        pixbuf3 = gtk.gdk.pixbuf_new_from_file('%s/windowsize.%s' %(self.out_dir, self.out_extension))
        pixbuf3 = pixbuf3.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure3.set_from_pixbuf(pixbuf3)
        pixbuf4 = gtk.gdk.pixbuf_new_from_file('%s/rto.%s' %(self.out_dir, self.out_extension))
        pixbuf4 = pixbuf4.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure4.set_from_pixbuf(pixbuf4)
        pixbuf5 = gtk.gdk.pixbuf_new_from_file('%s/bitrate.%s' %(self.out_dir, self.out_extension))
        pixbuf5 = pixbuf5.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure5.set_from_pixbuf(pixbuf5)
        
        
        pixbuf6 = gtk.gdk.pixbuf_new_from_file('%s/goodput.%s' %(self.out_dir, self.out_extension))
        pixbuf6 = pixbuf6.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure6.set_from_pixbuf(pixbuf6)
        
        pixbuf7 = gtk.gdk.pixbuf_new_from_file('%s/througput.%s' %(self.out_dir, self.out_extension))
        pixbuf7 = pixbuf7.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure7.set_from_pixbuf(pixbuf7)
        
        pixbuf8 = gtk.gdk.pixbuf_new_from_file('%s/requestedsize.%s' %(self.out_dir, self.out_extension))
        pixbuf8 = pixbuf8.scale_simple(FIGURE_WIDTH, FIGURE_HEIGHT, gtk.gdk.INTERP_BILINEAR)
        self.figure8.set_from_pixbuf(pixbuf8)
        
        
        self.figures_is_ready = False
    
    def stop(self):
        self.is_sample = False
        try:
            self.playerL.stop()
        except:
            print "playerL stops---"
        try:
            self.playerR.stop()
        except:
            print "playerR stops---"
            
        return 0
 


if __name__ == "__main__":    
    parser = argparse.ArgumentParser(description='Configure the arguments of this program')
    parser.add_argument("-m", "--show_movie", help="show the movie or not", dest="show_movie", action="store_false")
    #parser.add_argument("-g", "--show_gui", help="show gui or not", dest="show_gui", action="store_false")
    parser.add_argument("-f", "--show_figure", help="show monitoring figue or not", dest="show_figure", action="store_false")
     
    args = parser.parse_args()
    
    print args
    
    gui = Gui(args)
    gtk.quit_add(0, gui.stop)
    gtk.main()
    print "stop-"

