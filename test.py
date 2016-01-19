#!/usr/bin/env python

import sys, os
import pygtk, gtk, gobject
import pygst
pygst.require("0.10")
import gst

class GTK_Main:
    
    def __init__(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("Mpeg2-Player")
        window.set_default_size(500, 400)
        window.connect("destroy", gtk.main_quit, "WM destroy")
        vbox = gtk.VBox()
        window.add(vbox)
        hbox = gtk.HBox()
        vbox.pack_start(hbox, False)
        self.entry = gtk.Entry()
        hbox.add(self.entry)
        self.entry.set_text("media/a-sd.mp4")
        self.button = gtk.Button("Start")
        hbox.pack_start(self.button, False)
        self.button.connect("clicked", self.start_stop)
        
        
        self.movieL = gtk.DrawingArea()
        vbox.add(self.movieL)
        
        self.movieR = gtk.DrawingArea()
        vbox.add(self.movieR)
        
        
        window.show_all()

        
        self.pipeline = gst.Pipeline("pipeline")
        source = gst.element_factory_make("filesrc", "source")
        demuxer = gst.element_factory_make("qtdemux", "demuxer")
        demuxer.connect("pad-added", self.demuxer_callback)
        self.video_decoder = gst.element_factory_make("ffdec_h264", "video-decoder")
        self.audio_decoder = gst.element_factory_make("faad", "audio-decoder")
        audioconv = gst.element_factory_make("audioconvert", "converter")
        self.avolume = gst.element_factory_make("volume", "volume")
        #print self.avolume
        #self.avolume.set_property("mute", True)
        #self.avolume.set_volume(0.1)
        audiosink = gst.element_factory_make("autoaudiosink", "audio-output")
        
        vsize = gst.element_factory_make("videoscale", "videoscale")
        videosink = gst.element_factory_make("ximagesink", "video-output")
        self.queuea = gst.element_factory_make("queue", "queuea")
        self.queuev = gst.element_factory_make("queue", "queuev")
        colorspace = gst.element_factory_make("ffmpegcolorspace", "colorspace")
        
        self.pipeline.add(source, demuxer, self.video_decoder, self.audio_decoder, audioconv, self.avolume,
            audiosink, vsize, videosink, self.queuea, self.queuev, colorspace)
        gst.element_link_many(source, demuxer)
        gst.element_link_many(self.queuev, self.video_decoder, colorspace, vsize, videosink)
        gst.element_link_many(self.queuea, self.audio_decoder, audioconv, self.avolume, audiosink)
        self.location = None
        
        
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        
    def start_stop(self, w):
        
        if self.button.get_label() == "Start":
            filepath = self.entry.get_text()
            print "filepath=%s" %(filepath)
            if filepath != self.location:
                
                self.pipeline.set_state(gst.STATE_NULL)
                self.pipeline.get_by_name("source").set_property("location", filepath)
                print "change location to %s" %(self.pipeline.get_by_name("source").get_property("location"))
                self.location = filepath
                                
            self.pipeline.set_state(gst.STATE_PLAYING)
            self.button.set_label("Stop")
        else:
            self.pipeline.set_state(gst.STATE_PAUSED)
            self.button.set_label("Start")
            print "set ready"
                        
    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.pipeline.set_state(gst.STATE_NULL)
            self.button.set_label("Start")
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.pipeline.set_state(gst.STATE_NULL)
            self.button.set_label("Start")
    
    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            imagesink.set_xwindow_id(self.movieL.window.xid)
            imagesink.set_xwindow_id(self.movieR.window.xid)
            gtk.gdk.threads_leave()
    
    def demuxer_callback(self, demuxer, pad):
        if pad.get_property("template").name_template == "video_%02d":
            qv_pad = self.queuev.get_pad("sink")
            pad.link(qv_pad)
        elif pad.get_property("template").name_template == "audio_%02d":
            qa_pad = self.queuea.get_pad("sink")
            pad.link(qa_pad)
        
GTK_Main()
gtk.gdk.threads_init()
gtk.main()