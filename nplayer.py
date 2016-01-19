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
# Written by: Xiaoke Jiang <shock.jiang@gmail.com>

import pygtk
pygtk.require('2.0')
import pygst
pygst.require('0.10')

import gobject
import gtk
import gst
gobject.threads_init()
gtk.gdk.threads_init()

import platform
import logging
import os
import sys
import os.path
import threading
import thread
import time
import random
import Gnuplot

from ndn_flow import FlowConsumer, Controller, FlowConsumerThread


VIDEO_WIDTH = 460
VIDEO_HEIGHT = 250

SAMPLE_FREQ = 1/1.0

FIGURE_WIDTH = 300
FIGURE_HEIGHT = 250



PAPER = "nyplayer"

log = logging.getLogger("nplayer") #root logger, debug, info, warn, error, critical

#format = logging.Formatter('%(levelname)8s:%(funcName)23s:%(lineno)3d: %(message)s')
format = logging.Formatter('%(levelname)8s:%(module)10s:%(funcName)20s:%(lineno)3d: %(message)s')
fh = logging.FileHandler("nplayer.log", mode="w")
fh.setFormatter(format)

sh = logging.StreamHandler() #console
sh.setFormatter(format)

log.addHandler(sh)
log.addHandler(fh)

log.setLevel(logging.INFO)
#log.setLevel(logging.WARN)
#log.setLevel(logging.DEBUG)

class NDNSrc(threading.Thread):

    def __init__(self, chunksize=None,size_offset=0, window_fix=None, rtt_fix=None):
        threading.Thread.__init__(self)
        #gobject.GObjectMeta.__init__(self)
        
        #gst.Element.__init__(self)
        #gst.URIHandler.__init__(self)
        self.location = None#"/h243/chunksize/dir/c.mp3"
        
        
        self.flow = None
        self.chunksize = chunksize
        self.size_offset = size_offset
        self.window_fix =window_fix
        self.rtt_fix = rtt_fix
        self.Id = "win%s-chunksize%s-rtt%s" %(self.window_fix, self.chunksize, self.rtt_fix)
        #print self.ndn_name, type(self.ndn_name)
        
        
#         self.connect("need-data", self.need_data)
#         self.connect("enough-data", self.enough_data)
#         self.connect("seek-data", self.seed_data)
#         self.connect("end-of-stream", self.end_of_stream)

        #    def __init__(self, Id, ndn_name, fout=None, monitor_out_dir="output", enable_monitor=True, size_fix=None, window_fix=None, rtt_fix=None,
        #          packet_max_data_size=ETH_MTU-IP_HEADER_SIZE-UDP_HEADER_SIZE):
        
        self.index = 0
        self.first_run = True
        self.is_end = False

        
    def sample(self):
        if self.flow == None:
            return None, None, None, None, None
        OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rtos, TimeCost = self.flow.summary()
        
        timecost = TimeCost[0]
        #assert type(timecost) == int, "wrong type: %s" %(type(timecost))
        
        if self.first_run:
            self.first_run = False
            if timecost == 0:
                temp = 0
            else:
                temp = self.flow.mydata.accept_bytes/float(timecost)
            self.bitrates = [temp]
            self.goodputs = [self.flow.mydata.accept_bytes]
            accept_raw_bytes, requested_raw_bytes, = self.flow.sample2()
            self.throughputs = [accept_raw_bytes]
            self.requested_sizes = [requested_raw_bytes] 
            
            
        else:
            temp2 = timecost - self.last_time_cost
            if temp2 != 0:
                temp = (self.flow.mydata.accept_bytes-self.last_accept_bytes)/temp2
                
            else:
                temp = 0
            assert temp>=0, "bitrate=%s, accept_byets:%s, last accept bytes:%s, temp2:%s, %s" \
                %(temp, self.flow.mydata.accept_bytes, self.last_accept_bytes, temp2, type(self.last_accept_bytes))
            
            self.bitrates.append(temp)
            self.goodputs.append(self.flow.mydata.accept_bytes)
            
            accept_raw_bytes, requested_raw_bytes, = self.flow.sample2()
            self.throughputs.append(accept_raw_bytes)
            self.requested_sizes.append(requested_raw_bytes)
            
            
        self.last_time_cost = timecost
        self.last_accept_bytes = self.flow.mydata.accept_bytes
        if self.flow.is_all:
            self.is_end = True
            
        return OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rtos, self.bitrates, self.goodputs, \
            self.throughputs, self.requested_sizes
    
#     def run(self):
#         self.flow = FlowConsumerThread(Id=self.Id, name=self.location)
#         self.flow.start()
        
    def need_data(self, appsrc, need_bytes):   
        #self.emit("end-of-stream")
        if self.flow == None:
            return
        temp = "all" if self.flow.is_all else "requesting"
        if temp == "all":
            self.is_end = True
            
        name = appsrc.get_name()
        while self.flow.mydata.expected_chunkI <= self.index:
            if self.flow.is_all:
                appsrc.emit('end-of-stream')
                return
            
            time.sleep(1)
            
            
            log.debug("%s waiting data, player next need: %i, NDN expect:%i, total: %s, %s" 
              %(name, self.index, self.flow.mydata.expected_chunkI, self.flow.mydata.satisfied_chunkN, temp))
            
        
        chunkinfo = self.flow.chunkInfos[self.index]
        
        data = chunkinfo.content
        
        
        buffer = gst.Buffer(data)

        """gstream will showo critical message here, since caps is not valid (ANY)
        """
        #buffer.set_caps(caps)
        rst = appsrc.emit("push-buffer", buffer)
        
        
        if rst == gst.FLOW_OK:
            self.index += 1
            rst = ""
            log.debug("%s push-buffer back, player next need: %i, NDN expect:%i, total: %s, %s" 
                  %(name, self.index, self.flow.mydata.expected_chunkI, self.flow.mydata.satisfied_chunkN, temp))
        else:
            log.warn("%s fail to push-buffer back, %s, player next need: %i, NDN expect:%i, total: %s, %s" 
                  %(name, rst, self.index, self.flow.mydata.expected_chunkI, self.flow.mydata.satisfied_chunkN, temp))

    def set_location(self, value):        
        value = value.strip()
        if value != self.location:
            self.location = value
            self.index = 0
            if self.flow != None: #not the first time
                self.flow.stop()
            
            self.flow = FlowConsumerThread(Id=self.Id, name=self.location, size_fix=self.chunksize, size_offset=self.size_offset, window_fix=self.window_fix, rtt_fix=self.rtt_fix)
            self.flow.start()
            log.info("we start a new flow")
    
    def stop(self):
        if self.flow != None:
            self.flow.stop()
        #threading.Thread.__stop(self)
        return 0

class Player(threading.Thread):
    def __init__(self, gui, name):
        threading.Thread.__init__(self)
        self.gui = gui
        self.name = name
        
        size_offset = 0
        chunk_size = None
        window_fix = 50
        rtt_fix = float(4.0)
        if name == "L":
            pass
            #rtt_fix = None
            chunk_size = 4096
            #chunk_size = 6900
            #chunk_size = 5430
            #chunk_size = 3950
            #chunk_size = 2480
            #chunk_size = 1030
        else:
            #chunk_size = 4096 
            pass
        #rtt_fix = None
        #window_fix = None
        #chunk_size = 5000
        #size_offset = 0
        
            
        self.ndnsrc = NDNSrc(chunksize=chunk_size, size_offset=size_offset, window_fix=window_fix, rtt_fix=rtt_fix)
        
        
        
        
        
        
        self.pipeline = gst.Pipeline("mypipeline")
        self.src = gst.element_factory_make("appsrc", "source"+self.name)
        self.src.caps = gst.Caps("video/x-raw-gray,bpp=16,endianness=1234,width=320,height=240,framerate=(fraction)10/1")
        self.src.set_property("blocksize", 32*32*2)
        
        self.src.connect("need-data", self.ndnsrc.need_data)
        source = gst.element_factory_make("filesrc", "file-source")
        source = self.src
        
        
        demuxer = gst.element_factory_make("qtdemux", "demuxer")
        demuxer.connect("pad-added", self.demuxer_callback)
        self.video_decoder = gst.element_factory_make("ffdec_h264", "video-decoder")
        self.audio_decoder = gst.element_factory_make("faad", "audio-decoder")
        audioconv = gst.element_factory_make("audioconvert", "converter")
        self.avolume = gst.element_factory_make("volume", "volume")
        
        #self.avolume.set_property("mute", True)
        #self.avolume.set_volume(0.1)
        audiosink = gst.element_factory_make("autoaudiosink", "audio-output")
        
        
        vsize = gst.element_factory_make("videoscale", "videoscale")
        timeol = gst.element_factory_make("timeoverlay", "timeoverlay")
        thefont="Sans 24"
        timeol.set_property("font-desc", thefont)
        timeol.set_property("halign", "right")
        timeol.set_property("valign", "bottom")
        
        videosink = gst.element_factory_make("ximagesink", "video-output")
        #videosink = gst.element_factory_make("autovideosink", "video-output")
        self.queuea = gst.element_factory_make("queue", "queuea")
        self.queuev = gst.element_factory_make("queue", "queuev")
        colorspace = gst.element_factory_make("ffmpegcolorspace", "colorspace")
        
        self.pipeline.add(source, demuxer, self.video_decoder, self.audio_decoder, audioconv, self.avolume,
            audiosink, vsize, timeol, videosink, self.queuea, self.queuev, colorspace)
        gst.element_link_many(source, demuxer)
        gst.element_link_many(self.queuev, self.video_decoder, colorspace, vsize, timeol, videosink)
        gst.element_link_many(self.queuea, self.audio_decoder, audioconv, self.avolume, audiosink)
        
        
        
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        
        
        
        
        self.is_end = False
        self.is_all_data_cached = False
    
    def run(self):
        self.ndnsrc.start()

    def start_stop(self, cmd_label, location):
        if cmd_label == "Start":
            if self.ndnsrc.location != location:
                self.ndnsrc.set_location(location)
                self.pipeline.set_state(gst.STATE_NULL)
                self.ndnsrc.set_location(location)
            else:
                #self.ndnsrc.flow.change_status(Controller.STATUS_ON)
                pass    
            if self.gui.show_movie:
                self.pipeline.set_state(gst.STATE_PLAYING)
            
        else:
            if self.gui.show_movie:
                self.pipeline.set_state(gst.STATE_PAUSED)
    
    def on_message(self, bus, message):
        t = message.type
        #print "message_type: %s" %(t)
        if t == gst.MESSAGE_EOS:
            print "%s stream ends!! cool" %(self.name)
            self.pipeline.set_state(gst.STATE_NULL)
            self.ndnsrc.index = 0
            
            self.gui.on_message("end-of-stream")
            self.is_end = True
        elif t == gst.MESSAGE_ERROR:
            try:
                err, debug = message.parse_error()
            except:
                print "parse_error failed"
            print "Error: %s" % err, debug
            self.pipeline.set_state(gst.STATE_NULL)
    
    
    def mute(self, value):
        log.info("%s set mute %s" %(self.name, value))
        self.avolume.set_property("mute", value)
        
            
    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            #if not platform.system().startswith("Darwin"):
            #imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            
            if self.gui.show_movie:
                temp = self.gui.movieL
                print "set movie"
                if self.name == "R":
                    temp = self.gui.movieR
                if temp != None:
                    movie_window = temp.window.xid
                    imagesink.set_xwindow_id(movie_window)
                else:
                    log.critical("could not allocat a window for player: %s" %(self.name))
            else:
                
                print "don't show"
            #print "set window.id=%s" %(self.gui.movieL.window.xid)
            gtk.gdk.threads_leave()
    
    def set_state(state):#state in [gst.STATE_PLAYING, gst.STATE_NULL]
        self.pipeline.set_state(state)

    def demuxer_callback(self, demuxer, pad):
        if pad.get_property("template").name_template == "video_%02d":
            qv_pad = self.queuev.get_pad("sink")
            pad.link(qv_pad)
        elif pad.get_property("template").name_template == "audio_%02d":
            qa_pad = self.queuea.get_pad("sink")
            pad.link(qa_pad)
        
        
    
    def sample(self):
        """probably may be None if there is error or not start yet.
        """
        OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rtos, BitRates, Goodputs, Throughputs, RequestedSizes= self.ndnsrc.sample()
        return OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rtos, BitRates, Goodputs, Throughputs, RequestedSizes
    
    def stop(self):
        self.ndnsrc.stop()
        #threading.Thread.__stop(self)
        return 0
