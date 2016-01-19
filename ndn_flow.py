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


# todo: 
#1) final chunk, the packetN != chunkinfo.packetN-----check
#2) monitor the chunk size, window size -----check
#3) rtt and rtte
#4) multiple hops of NDN nodes
#5) detect whether nothing received, or something, or all the data


import logging
import datetime
import os
import os.path
import sys
import signal
import math
import types
import collections
import time
import threading

import pyndn
from pyndn import _pyndn

PAPER = "ndnFlow" #project ndn_name to use FlowConsumer, and log file is <PAPER>.log


IP_HEADER_SIZE = 20
UDP_HEADER_SIZE = 8
TCP_HEADER_SIZE = 20
ETH_MTU = 1500

DEFAULT_DATA_SIZE = 5448

CHUNK_HEADER_SIZE = 410 #about, if the ndn_name is quite long, the size should be larger
#CHUNK_HEADER_SIZE = 436 #about, if the ndn_name is quite long, the size should be larger
MAX_DATA_SIZE = 8350 #when chunk size is bigger than 9000, the consumer cannot receive the chunk, 8370 is the max, leave some for ndn_name
#MAX_DATA_SIZE = 7040 #when chunk size is bigger than 9000, the consumer cannot receive the chunk, 8370 is the max, leave some for ndn_name
#8392(more, we use 8350 for max size of ndnx),6920(1%), 5448(2%),3976(3%), 2504(5%), 1032(12%)
#MAX_DATA_SIZE = 10000
INITIAL_CHUNK_SIZE = 4096



DEFAULT_INTEREST_LIFETIME = float(1.0) #must be float
DEFAULT_NDN_RUN_TIMEOUT = 1000 #microseconds

MAX_WINDOWSN = 150 #for slide window mechanism

ADAPTIVE_MOD_FLAG = "<adaptive>" #this is embeded in Interest.name to tell consumer the data_size which is recommended by consumer

log = logging.getLogger("ndnFlow") #root logger, debug, info, warn, error, critical

#format = logging.Formatter('%(levelname)8s:%(funcName)23s:%(lineno)3d: %(message)s')
format = logging.Formatter('%(levelname)8s:%(module)10s:%(funcName)20s:%(lineno)3d: %(message)s')
fh = logging.FileHandler(PAPER+".log", mode="w")
fh.setFormatter(format)

sh = logging.StreamHandler() #console
sh.setFormatter(format)

log.addHandler(sh)
log.addHandler(fh)

log.setLevel(logging.DEBUG)
#log.setLevel(logging.INFO)
#log.setLevel(logging.WARN)
#log.setLevel(logging.CRITICAL)

class Monitor(object):
    def __init__(self, Id, out_dir):
        self.Id = Id
        self.out_dir = out_dir
        self.vars = []
        self.vars2 = []
        
    def sample(self):
        """wait for override and is called when status updated (update_loss, update_receiving or get_optimal_data_size)
        """
        pass
    
    def _output(self, outpath, li, tags):
        fout = open(outpath, "w")
        fout.write("#")
        for tag in tags:
            fout.write(tag+"\t")
        fout.write("\n")
        for i in range(len(li)):
            val = li[i]
            fout.write("%s\t%s\n" %(i+1, val))
            
        fout.close()
        
    def show(self):
        """wait for override
            outpath, file to output
        """
        pass
    

class MyData(Monitor):
    """hold the status data when FlowConsumer is running
    
    Attributes:
        next_byte: the byte sequence that FlowConsumer requests
        final_byte: when Data contained final_block_id information, the final_byte is filled. When next_byte== final_byte, all the data received
        unsatisfied_chunks_keyed_by_name: those chunks have been requested, including re-expressing Interest, but not satisfied yet 
    """
    
    def __init__(self):
        self.beginT = datetime.datetime.now()
        self.endT = None
        self.next_byte = 0
        self.final_byte = None
        self.accept_bytes = 0# data size
        self.accept_raw_bytes = 0 # all the received bytes
        self.request_raw_bytes = 0 # according to the Interest
        self.expected_chunkI = 0 # the chunk index in the chunkinfos which is expecting to be satisfied
        self.satisfied_chunkN = 0 # the total number of chunks which is already satisfied
        self.unsatisfied_chunks_keyed_by_name = collections.OrderedDict() #chunkinfo key by ndn_name, the dictionary is ordered by the insertion order
        
        
    def __str__(self):
        temp = self.get_time_cost()    
        if temp == 0:
            bitrate = 0
        else:
            bitrate = self.accept_raw_bytes/float(temp)
        return "timecost=%s accept_bytes=%s final_byte=%s accept_raw_byte=%s requested_raw_byte=%s satisfied_chunkN=%s unsatisfied_chunksN=%s bitrate=%s" %(
                temp, self.accept_bytes, self.final_byte, self.accept_raw_bytes, self.request_raw_bytes, 
                self.satisfied_chunkN, len(self.unsatisfied_chunks_keyed_by_name), bitrate)
    
    def get_time_cost(self):
        temp = None
        
        
        if self.endT != None:
            t2 = self.endT
        else:
            t2 = datetime.datetime.now()
                
        temp2 = t2 - self.beginT
        temp = temp2.days * 24 * 3600 + temp2.seconds + temp2.microseconds/1000000.0
        return temp
    
    def sample(self):
        pass
    
    def show(self):
        pass

class ChunkInfo(object):
    """Chunk's Information
    
    Attributes:
        beginT: the time that chunk is requested (Interest Sent)
        begin_byte: the begin_byte of the chunk
        end_byte: the end_byte of the chunk, thus, chunk_size = end_byte - begin_byte + 1
        packetN: the number of underlying packet, this is expected number, but not the real number(final chunk, illegal chunk)
        
        reTxN: number of retransmission, if no retransmission, reTxN == 1
        
        endT: the time that chunk is received (Data Received)
        data_size: size applicaiton data contained in the chunk
        chunk_size: the whole size of the chunk, contained chunk header, signature, etc.
    """
    
    def __init__(self):
        
        #follwoing attributes are filled when instance is created, first_express_interest fill it
        self.beginT = None
        self.begin_byte = None
        self.end_byte = None
        self.packetN = None
        
        #this attribute is updated during transmission and retransmission, express_interest change it.
        self.retxN = 0
        self.status = 1 #1 means being sent, 0 mean being suppressed and waiting, 2 means satisfied
        self.lifetime = None
        
        #the following attributes are filled when content is receieved, do_receive_content fill it
        self.endT = None
        self.data_size = None
        self.chunk_size = None

    
    def __str__(self):
        return "beginT=%s, begin_byte=%s, endT=%s, end_byte=%s, packetN=%s, retxN=%s, data_size=%s, chunk_size=%s, status=%s" \
            %(self.beginT, self.begin_byte, self.endT, self.end_byte, self.packetN, self.retxN, self.data_size, self.chunk_size, self.status)

    
class SlideWindow(Monitor):
    """manage the congestion window
    Implemenation ref to "TCP Congestion Control" p571-580, Computer Networks(ed 5), by Andrew S. Tanenbaum and David J. Wetherall
    
    packet_on_the_fly management:
        add: first_express and re_express
        reduce: nack, in_order_content, out_of_order_content and timeout
    
    Attributes:
        threshold: threshold of congestion window, measured by packet number
        _cwnd: current size of congestion window, measured by packet number of underlying network (UDP/IP/Ethernet). private variable, since it may be a float. 
            we call NDN layer datagram "chunk" and leave "packet" donate to datagram of underlying network
        packet_on_the_fly: number of packets which has been requested but not received
        is_fix: whether to return a fix number evey time or not. None means not, a integer value means yes
    """
    
    def __init__(self, Id, out_dir, enable_monitor, is_fix=None, **kwargs):
        Monitor.__init__(self, Id, out_dir)
        self.threshold = 10000#sys.maxint
        
        self.packet_on_the_fly = 0
        self.enable_monitor = enable_monitor
        self.mydata = kwargs.get("mydata", None)
        
        if is_fix != None:
            assert type(is_fix) == types.IntType, "illegal is_fix type: %s" %(str(is_fix))
        self.is_fix = is_fix #if is_fix is a integer, then the optimal_data_size return the fix integer value every time
        self._cwnd = 0# if self.is_fix==None else self.is_fix 
        
        self.suppress_endT = None
        #measured by number of underlying network packet, can be float during additive increase stage
        #self.wait_re_express =  
        self.suppress_endT = None
        self.sample()
        
    def __str__(self):
        return "threshold:%s, cwnd:%s, packet_on_the_fly:%s" %(self.threshold, self._cwnd, self.packet_on_the_fly)
    
    #overrides(Monitor)
    def sample(self):
        if not self.enable_monitor:
            return
        if self.is_fix == None:
            self.vars.append(self._cwnd)
        else:
            self.vars.append(self.is_fix)
        
    #overrides(Monitor)
    def show(self):
        if not self.enable_monitor:
            return
        
        li = self.vars
        tags = ["ChunkReceivedOrder", "CongestionWindowSize"]
        outpath = os.path.join(self.out_dir, self.Id+"-winsize.txt")
        self._output(outpath, li, tags)
        return self.vars
        
    def get_cwnd(self):
        """return integer value"""
        
        self.sample()
        if self.is_fix != None:
            return self.is_fix
        else:
            return int(self._cwnd)
    
    def update_express(self, chunkinfo):
        self.packet_on_the_fly += chunkinfo.packetN
    
    def update_nack(self, chunkinfo):
        #we don't increase window, due to near end, we do need to make window larger
        self.packet_on_the_fly -= chunkinfo.packetN
        log.warn("a nack received, chunkinfo=%s" %(chunkinfo))
        
    def update_loss(self, chunkinfo):
        self.packet_on_the_fly -= chunkinfo.packetN
        
        if chunkinfo.retxN > 1:
            return
        
#         if self.suppress_endT != None and self.suppress_endT < datetime.datetime.now():
#             self.suppress_endT = chunkinfo.beginT + datetime.timedelta(seconds=0.5)
#         
        #if self.is_fix == None:
        self._cwnd = int(self._cwnd/2.0) #sawtooth
        if self._cwnd < 1:
            self._cwnd = 1
            
        self.threshold = self._cwnd #fast recovery
        log.debug("change cwnd to %s, threshold to %s, packet_on_the_fly to %s" %(self._cwnd, self.threshold, self.packet_on_the_fly))
        #self.sample()
        
    def update_duplicate4(self, chunkinfo):
        if self._cwnd == 0:
            self._cwnd = 1
        else:
            if self.is_fix == None:
                if self._cwnd < self.threshold:
                    self._cwnd += chunkinfo.packetN #slow start
                else:
                    self._cwnd += chunkinfo.packetN * 1.0/self._cwnd #additive increase
                if self._cwnd > MAX_WINDOWSN:
                    self._cwnd = MAX_WINDOWSN
        #self.sample()
        log.debug("duplicate4 change cwnd to %s, threshold to %s, packet_on_the_fly to %s" %(self._cwnd, self.threshold, self.packet_on_the_fly))
        
    def update_receiving(self, chunkinfo):
        self.packet_on_the_fly -= chunkinfo.packetN
        if self._cwnd == 0:
            self._cwnd = 1
        else:
            if self.is_fix == None:
                if self._cwnd < self.threshold:
                    self._cwnd += chunkinfo.packetN #slow start
                else:
                    self._cwnd += chunkinfo.packetN * 1.0/self._cwnd #additive increase
                if self._cwnd > MAX_WINDOWSN:
                    self._cwnd = MAX_WINDOWSN
        #self.sample()
        log.debug("change cwnd to %s, threshold to %s, packet_on_the_fly to %s" %(self._cwnd, self.threshold, self.packet_on_the_fly))
        
        
class RtoEstimator(Monitor):
    """according to rfc6298: http://tools.ietf.org/html/rfc6298 the latest rfc on rto estimation
    """
    RTT_ALPHA = 1.0/8
    RTT_BELTA = 1.0/4
    RTT_INITIAL_RTO = float(1.0)
    RTT_G = 0.1
    RTT_K = 4
    RTT_RTO_MAX = 4.0
    def __init__(self, Id, out_dir, is_fix, enable_monitor):
        #self.rttEstimator = RtoEstimator(Id=self.Id, out_dir=self.monitor_out_dir, is_fix=rtt_fix)    
        Monitor.__init__(self, Id, out_dir)
        self.enable_monitor = enable_monitor
        self.is_fix = is_fix
        if self.is_fix != None and self.is_fix > RtoEstimator.RTT_RTO_MAX:
            RtoEstimator.RTT_RTO_MAX = self.is_fix
        
        self._rto = RtoEstimator.RTT_INITIAL_RTO#DEFAULT_INTEREST_LIFETIME if self.is_fix==None else self.is_fix
        self._srtt = None#DEFAULT_INTEREST_LIFETIME if self.is_fix==None else self.is_fix
        self._rttvar = None
        
        #self.sample()
    
    def __str__(self):
        return "RTO=%s, SRTT=%s, RTTVar=%s" %(self._rto, self._srtt, self._rttvar)
    
    def sample(self):
        if not self.enable_monitor:
            return
        
        if self.is_fix == None:
            self.vars.append(self._rto)
        else:
            self.vars.append(self.is_fix)
            
    #overrides(Monitor)
    def show(self):
        """fout, file to output
            mode: txt, write data to txt,
                  fig: draw a figure
        """
        if not self.enable_monitor:
            return
        li = self.vars
        tags = ["InterestGeneratedOrder", "RTT"]
        outpath = os.path.join(self.out_dir, self.Id+"-rtt.txt")
        self._output(outpath, li, tags)
        return self.vars
        
    def get_rto(self):
        self.sample()
        if self.is_fix == None:
            return self._rto
        else:
            return self.is_fix
    
    def adjust_to_ndn_model(self, rto, srtt, rttvar):
        self._rto =  rto * 2
        pass
    
    def update(self, chunkinfo):
        if chunkinfo.retxN > 1:#do not use the retransmitted chunks
            return
        
        assert chunkinfo.retxN == 1
        R = chunkinfo.endT - chunkinfo.beginT
        R = R.days*24*3600 + R.seconds + R.microseconds/1000000.0 #float seconds
        #assert R <= RtoEstimator.RTT_RTO_MAX, "R=%s"%(R)
        
        if self._srtt == None: # the first time
            self._srtt = R
            self._rttvar = R/2
            
        else:
            self._rttvar = (1-RtoEstimator.RTT_BELTA) * self._rttvar + RtoEstimator.RTT_BELTA * abs(self._srtt - R)
            self._srtt = (1-RtoEstimator.RTT_ALPHA) * self._srtt + RtoEstimator.RTT_ALPHA * R
        
        
        temp = 4 * self._rttvar
        if temp < RtoEstimator.RTT_G:
                temp = RtoEstimator.RTT_G
        
        self._rto = self._srtt + temp
            
        self.adjust_to_ndn_model(self._rto, self._srtt, self._rttvar)
        if self._rto < 1.0:
            self._rto = 1.0
        elif self._rto > RtoEstimator.RTT_RTO_MAX:
            self._rto = RtoEstimator.RTT_RTO_MAX

    def update_loss(self, chunkinfo):
        #self._rttvar = self._rto
        self._rto = self._rto * 2
        if self._rto > RtoEstimator.RTT_RTO_MAX:
            self._rto = RtoEstimator.RTT_RTO_MAX
class ChunkSizeEstimator(Monitor):
    """estimate the optimal chunk size, according to Xiaoke Jiang's paper
    
    Attributes:
        receivedN: packet received
        lostN: packet lost
        packet_max_data_size: the max data (NDN Layer's Data) size of the packet, typcally, 1472, (1500 - 20 - 8)
        mode: measured by chunk or by underlying packet
        is_fix: whether to return a fix number evey time or not. None means not, a integer value means yes
    """
    
    def __init__(self, Id, out_dir, packet_max_data_size, enable_monitor, mode="chunk", is_fix=None, size_offset=0, chunk_header_size=500, trialN=150, **kwargs):
        Monitor.__init__(self, Id, out_dir)
        self.enable_monitor = enable_monitor
        self.mode = mode
        self.receivedN = 0
        self.lostN = 0
        self.packet_max_data_size = packet_max_data_size
        self.chunk_header_size = chunk_header_size
        self.timeout_istN = 0
        self.received_chunkN = 0
        self.trialN = trialN
        self._loss_rate = 0
        self.mydata = kwargs.get("mydata", None)
        
        if is_fix != None:
            assert type(is_fix) == types.IntType, "illegal is_fix type: %s" %(str(is_fix))
        self.is_fix = is_fix #if is_fix is a integer, then the optimal_data_size return the fix integer value every time
        self.size_offset = size_offset #this only works when is_fix == None
        self._optimal_size = INITIAL_CHUNK_SIZE if self.is_fix == None else self.is_fix
        
        self._last_chunk_size = INITIAL_CHUNK_SIZE
        self._next_critical_point =  self.trialN / math.ceil(self._last_chunk_size/self.packet_max_data_size)
        
        self.sample()
    
    def __str__(self):
        return "receivedN=%s, lostN=%s, loss_rate=%s, optimal_size=%s" %(self.receivedN, self.lostN, self._loss_rate, self._optimal_size)
    
    def get_loss_rate2(self):
        if self.mode == "packet":
            temp =float(self.timeout_istN)/( self.timeout_istN + self.received_chunkN)
        elif self.mode == "chunk":
            temp = float(self.lostN)/(self.receivedN + self.lostN)
        return temp
    
    #overrides(Monitor)
    def sample(self):
        if not self.enable_monitor:
            return
        self.vars.append(self._optimal_size)
        if self.mode == "packet":
            self.vars2.append(self._loss_rate)
        else:
            temp = self.timeout_istN + self.received_chunkN
            if temp == 0:
                temp2 = 0
            else:
                temp2 = self.timeout_istN / float(temp)
            self.vars2.append(temp2)
    
    
    
    
    #overrides(Monitor)
    def show(self):
        """fout, file to output
            mode: txt, write data to txt,
                  fig: draw a figure
        """
        if not self.enable_monitor:
            return
        li = self.vars
        tags = ["InterestGeneratedOrder", "OptimalDataSize"]
        outpath = os.path.join(self.out_dir, self.Id+"-chunksize.txt")
        self._output(outpath, li, tags)
        
        li = self.vars2
        tags = ["InterestGeneratedOrder", "PacketLossRate"]
        outpath = os.path.join(self.out_dir, self.Id+"-lossrate.txt")
        self._output(outpath, li, tags)
        return self.vars, self.vars2
    
    def _get_loss_rate(self):
        if self.mode == "packet":
            loss_rate = float(self.lostN)/(self.receivedN + self.lostN)  # 1- \omega 
        elif self.mode == "chunk":
            loss_rate = float(self.timeout_istN)/( self.timeout_istN + self.received_chunkN)
        
        return loss_rate
        
    def get_optimal_data_size(self):
        """only data, not including the chunk header size
        
        Return:
            chunk_data_size: the size of data contained in a chunk, chunk header/signature ... are not included
        """
        if self.lostN == 0:
            if self.mydata.expected_chunkI > self._next_critical_point:
                if self.is_fix == None:
                    msg = "chunksize=%s currentpoint=%s atpoint=%s acceptN=%s unsatN=%s" %(self._last_chunk_size, self._next_critical_point, self.mydata.expected_chunkI, self.mydata.expected_chunkI, len(self.mydata.unsatisfied_chunks_keyed_by_name))
                    log.debug(msg)
                    print "lostN=0", msg
                    for key in self.mydata.unsatisfied_chunks_keyed_by_name.keys():
                        print key
                self._last_chunk_size += self.packet_max_data_size
                if self._last_chunk_size > MAX_DATA_SIZE:
                    self._last_chunk_size = MAX_DATA_SIZE
                
                self._next_critical_point = self.mydata.satisfied_chunkN + len(self.mydata.unsatisfied_chunks_keyed_by_name) + self.trialN/ math.ceil((self._last_chunk_size/self.packet_max_data_size))
                
                chunk_data_size = self._last_chunk_size
              
            else:
                chunk_data_size = self._last_chunk_size
                if self.is_fix == None:
                    print chunk_data_size
        else:
            #ref to: 
            loss_rate = self._get_loss_rate()
            
            self._loss_rate = loss_rate
            
            T = 1 - loss_rate
            
            D = self.chunk_header_size #\Delta
            M = self.packet_max_data_size
            
            chunk_data_size = (-1*D*math.log(T) -pow((D*(math.log(T)))**2-4*M*math.log(T)*D, 0.5))/(2*math.log(T)) #data size of the chunk
            
            k = int ((self.chunk_header_size + chunk_data_size) / M)
            temp = k
            r1 = (T**temp) * (temp * M) / (self.chunk_header_size + temp*M)
            
            temp = k+1
            r2 = (T**temp) * (temp * M) / (self.chunk_header_size + temp*M)
            
            if r1 > r2:
                chunk_data_size = k * M - self.chunk_header_size
            else:
                chunk_data_size = (k+1) * M - self.chunk_header_size
            
            
            if chunk_data_size > MAX_DATA_SIZE:
                chunk_data_size = MAX_DATA_SIZE
            
            if chunk_data_size > self._last_chunk_size:
                if self.mydata.expected_chunkI > self._next_critical_point:
                    if self.is_fix == None:
                        msg = "chunksize=%s currentpoint=%s atpoint=%s acceptN=%s unsatN=%s" %(self._last_chunk_size, self._next_critical_point, self.mydata.expected_chunkI, self.mydata.expected_chunkI, len(self.mydata.unsatisfied_chunks_keyed_by_name))
                        print "lostrat=%s" %(lossrate), msg
                    self._last_chunk_size = chunk_data_size
                    
                    self._next_critical_point = self.mydata.satisfied_chunkN + len(self.mydata.unsatisfied_chunks_keyed_by_name) + self.trialN/ math.ceil((self._last_chunk_size/self.packet_max_data_size))      
                else:
                    chunk_data_size = self._last_chunk_size
                    
        chunk_data_size += self.size_offset
            
        self._optimal_size = chunk_data_size
        
        if self.is_fix != None:
            chunk_data_size = self.is_fix
            self._optimal_size = chunk_data_size
        if self.is_fix == None and self._optimal_size != chunk_data_size:
            log.debug("optimal chunk data size: %s, loss rate: %s" %(chunk_data_size, self._loss_rate))
        
        self.sample()
        return chunk_data_size

    
    def update_loss(self, chunkinfo):
        self.lostN += 1
        self.receivedN += chunkinfo.packetN - 1
        self.timeout_istN += 1
        
        #in case no data is coming at all, retx does not need get the optimal chunk size
        # in which case, loss rate keeps to be zero
        #self.sample()
        
        
    def update_receiving(self, chunkinfo):
        self.receivedN += chunkinfo.packetN
        self.received_chunkN += 1
    
    def change_chunk_header_size(self, new_size):
        self.chunk_header_size = new_size
        
        
class Controller(object):        
    STATUS_ON = 1
    STATUS_OFF = 2
    STATUS_STEP_ON = 3
    STATUS_STEP_OFF = 4
    
    def __init__(self):
        self.status = Controller.STATUS_ON
    
    def chang_status(self, new_status):
        self.status = new_status
        
class FlowConsumer(pyndn.Closure, Controller):
    """Continuously request Data, with TCP congestion control mechanism and optimal chunk size estimation
    
    Attributes:
        status: whether it works or not
        ndn_name: ndn_name prefix of the data
        fout: the received content will write to the fout, make sure fout has the "write" method, fout.write("<the content>")
        size_fix: whether to return a fix number evey time or not. None means not, a integer value means yes
        window_fix:  whether to return a fix number evey time or not. None means not, a integer value means yes
        packet_max_data_size: the max data (NDN Layer's Data) size of the packet, typcally, 1472, (1500 - 20 - 8)
        is_all: whether already fetch all the contents or not
    """
    
    def __init__(self, Id, name, fout=None, monitor_out_dir="output", cache_data=True, enable_monitor=True, size_fix=None, size_offset=0, window_fix=None, rtt_fix=None,
                  split_fix=4097, packet_max_data_size=ETH_MTU-IP_HEADER_SIZE-UDP_HEADER_SIZE):
        """
        """
        Controller.__init__(self)
        
        self.Id = Id
        if monitor_out_dir == None:
            monitor_out_dir = "output"
        self.monitor_out_dir = monitor_out_dir
        if not os.path.exists(self.monitor_out_dir):
            os.makedirs(self.monitor_out_dir)
        
        
        if not name.startswith("ndnx:") and not name.startswith("/"):
            name = "/" + name
            
        self.chunk_header_size = CHUNK_HEADER_SIZE + len(name) + 30
        
        self.ndn_name = pyndn.Name(name)
        """since there is a "name" field in threading.Thread, we name it as ndn_name
        """
        self.cache_data = cache_data
        self.fout = fout
        if self.fout == None:
            self.fout = os.path.join(".", "acquire")
            if not os.path.exists(self.fout):
                os.makedirs(self.fout)
                
            self.fout = os.path.join(self.fout, name.replace("/", "-")[1:])
            #self.fout = os.path.join(self.fout, Id)
            self.fout = open(self.fout, "w")
        self.size_fix = size_fix
        self.size_offset = size_offset
        self.window_fix = window_fix
        self.split_fix = split_fix
        self.packet_max_data_size = packet_max_data_size
        self._out_of_orderN = 0 
        self.is_all = False #already fetch all the chunks,
        
        self.handle = pyndn.NDN()
        
        self.chunkInfos = []#only insert new elements when first_express_interest

        self.mydata = MyData()
        trialN = 150
        if self.window_fix != None:
            trialN = self.window_fix * 3
            if trialN < 100:
                trialN = 100
        self.chunkSizeEstimator = ChunkSizeEstimator(Id=self.Id, out_dir=self.monitor_out_dir, packet_max_data_size=self.packet_max_data_size, is_fix=size_fix, 
                                                     size_offset=self.size_offset, enable_monitor=enable_monitor, trialN=trialN, mydata=self.mydata)
        self.window = SlideWindow(Id=self.Id, out_dir=self.monitor_out_dir, is_fix=window_fix, enable_monitor=enable_monitor)
        self.rtoEstimator = RtoEstimator(Id=self.Id, out_dir=self.monitor_out_dir, is_fix=rtt_fix, enable_monitor=enable_monitor)
        
        
    def start(self):
        """a big different with the way, self.handle.run(-1), which cann't catch the signal interrupt all all, even if its parent thread
            however, with while loop check, the parent thread can catch the signal, for the whole process won't sink in self.handle.run()
        """
        log.warn("%s begin to request %s" %(self.Id, self.ndn_name))
        self.status = Controller.STATUS_ON
        self.first_express_interest()
        self.handle.run(DEFAULT_NDN_RUN_TIMEOUT)
        
        if self.window_fix == None:
            self.first_express_interest()
        else:
            while self.window.packet_on_the_fly < self.window.get_cwnd():
                self.first_express_interest()
            
        while self.status != Controller.STATUS_OFF:
            #print "test! status=%s" %(self.status)
            if self.status == Controller.STATUS_ON:
                self.handle.run(DEFAULT_NDN_RUN_TIMEOUT)
            elif self.status == Controller.STATUS_STEP_ON:
                self.handle.run(DEFAULT_NDN_RUN_TIMEOUT)
                self.status = Controller.STATUS_STEP_OFF
            elif self.status == Controller.STATUS_STEP_OFF:
                time.sleep(1)

        return self.is_all
                
    def __str__(self):
        temp = "requestedChunkN=%s" %(len(self.chunkInfos)) +", "+ str(self.mydata) +", "+\
            str(self.window) + ", " + str(self.chunkSizeEstimator)
        return temp
    
                 
    def stop(self):
        self.status = Controller.STATUS_OFF
        """this is important, since we don't want to call stop twice.
            stop is called implicitly in in_order_content when consuemr acquire all the contents
            thus, when upper layer application call stop, it won't cause any problem, like fout is closed
            
            meanwhile, we don't suggest upper layer applications change the status
        """
            
        if _pyndn.is_run_executing(self.handle.ndn_data):
            self.handle.setRunTimeout(1)
        
        
        if not self.fout.closed:
            self.mydata.endT = datetime.datetime.now()
            self.fout.flush()
            self.fout.close()
        
         
        if threading.currentThread().is_alive():
            log.info("%s stops!" %(self.Id))
            log.info("requestedChunkN=%s" %(len(self.chunkInfos)))
            log.info(str(self.mydata))
            log.info(str(self.window))
            log.info(str(self.chunkSizeEstimator))
            log.info("chunk_header_size=%s" %(self.chunk_header_size))
        
        return 0
        
        
    def summary(self):
        outpath = id
        OptimalChunkSizes, PacketLossRates = self.chunkSizeEstimator.show()
        CongestionWindowSizes = self.window.show()
        Rto = self.rtoEstimator.show()
        TimeCost = self.mydata.get_time_cost()
        return OptimalChunkSizes, PacketLossRates, CongestionWindowSizes, Rto, [TimeCost]
    
    def sample2(self):
        return self.mydata.accept_raw_bytes, self.mydata.request_raw_bytes
    
    def try_express_interest(self, chunkinfo=None):
        pass
    def re_express_interest(self, chunkinfo):
        if self.status == Controller.STATUS_OFF or self.status == Controller.STATUS_STEP_OFF:
            return
        
        if self.mydata.final_byte !=None and chunkinfo.begin_byte >= self.mydata.final_byte: #suppress the illegal reuqest 
            log.debug("illegel request, do not re-express it: %s" %(chunkinfo.ndn_name))
        elif self.is_all:#shouldn't happen, since already check before re-expressing
            log.error("already get all the requests, do not re-express it: %s" %(chunkinfo.ndn_name))
        else:
            self.window.update_express(chunkinfo)
            self.express_interest(chunkinfo)
    
    def first_express_interest(self):
        if self.status == Controller.STATUS_OFF or self.status == Controller.STATUS_STEP_OFF:
            return
        if self.mydata.final_byte != None and self.mydata.next_byte >= self.mydata.final_byte:
            #we do not use is_all to check, since final_byte is more accurate and is_all -> final_byte
            log.debug("illegel request, do not express it, next_byte: %s" %(self.mydata.next_byte))
            return
        
        chunkinfo = ChunkInfo()
        chunkinfo.beginT = datetime.datetime.now()
        
        chunkinfo.begin_byte = self.mydata.next_byte
        temp = self.chunkSizeEstimator.get_optimal_data_size()
        chunkinfo.end_byte = chunkinfo.begin_byte +  temp - 1
        chunkinfo.data_size = temp
        chunkinfo.chunk_size = temp + self.chunk_header_size
        
        chunkinfo.packetN = math.ceil((temp + self.chunk_header_size)/float(self.packet_max_data_size))
        chunkinfo.status = 1
        
        name = self.ndn_name
        
        name = self.ndn_name.append(ADAPTIVE_MOD_FLAG).append(str(temp)) #only leave the data size
        name = name.append(chunkinfo.begin_byte)
        chunkinfo.ndn_name = name
        
        
        self.chunkInfos.append(chunkinfo)
        self.mydata.unsatisfied_chunks_keyed_by_name[str(name)] = chunkinfo
        
        #packet_on_the_fly, 3 results, illegal, out-of-order, in-order and retransmission
        self.window.update_express(chunkinfo)
        
        self.express_interest(chunkinfo)
        self.mydata.next_byte = chunkinfo.end_byte + 1
        
    def express_interest(self, chunkinfo):
        """this method may express illegal Interest, thus, re_express_interest and first_express_interest are in charge of checking;
            even that, there may also illegal Interest, due to unknown final_byte, leading to useless chunkinfo in chunkinfos and illegal Data(Nack) or Interest timeout
                 (we do not use is_all to check, since final_byte is more accurate and is_all -> final_byte);
            thus, we need do_receiving_content to handle illegal Data
        """
        assert chunkinfo != None, "chunkinfo == None"
        assert chunkinfo.endT == None, "chunkinfo.endT != None"
        
        
        selector = pyndn.Interest()
        selector.answerOriginKind = 0#producer generate every time
        selector.childSelctor = 1
        selector.interestLifetime = self.rtoEstimator.get_rto()
        rst = self.handle.expressInterest(chunkinfo.ndn_name, self, selector)
        chunkinfo.lifetime = selector.interestLifetime
        
        
        self.mydata.request_raw_bytes += chunkinfo.chunk_size
        
        if rst != None and rst < 0:        
            log.warn("fail to express interest=%s with result %s" %(chunkinfo.ndn_name, rst))
            self.window.update_nack(chunkinfo)
            chunkinfo.status = 0

        else:
            chunkinfo.retxN += 1        
            log.debug("express interest=%s" %(chunkinfo.ndn_name))
        
    def upcall(self, kind, upcallInfo):
        if kind == pyndn.UPCALL_FINAL:#handler is about to be deregistered
            
            #if self.status and not self.is_all:    
                #self.handle.setRunTimeout(DEFAULT_NDN_RUN_TIMEOUT)
                #log.error("handler is about to be deregistered, reset it." )    
            
            return pyndn.RESULT_OK

        if kind in [pyndn.UPCALL_INTEREST, pyndn.UPCALL_CONSUMED_INTEREST]:
            log.error("unexpected kind: %s" %kind)
            return pyndn.RESULT_OK
        
        if kind == pyndn.UPCALL_INTEREST_TIMED_OUT:
            self.do_meet_accident(kind, upcallInfo)
            return pyndn.RESULT_OK
        
        if kind in [pyndn.UPCALL_CONTENT_UNVERIFIED, pyndn.UPCALL_CONTENT_BAD]:
            self.do_meet_accident(kind, upcallInfo)
            return pyndn.RESULT_OK
        

        
        assert kind == pyndn.UPCALL_CONTENT, "kind: "+str(kind)
        
        self.do_receive_content(kind, upcallInfo)
        
        return pyndn.RESULT_OK
    
    def do_meet_accident(self, kind, upcallInfo):
        name = str(upcallInfo.Interest.name)
        if not name in self.mydata.unsatisfied_chunks_keyed_by_name:
            #since it's not possible that two same Interest on the fly at the same time, it sholdn't happen 
            log.error("timeout Interest not in the unsatisfied list, it should not happend: %s!!" %(name))
            return
        
        chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name[name]
        self.chunkSizeEstimator.update_loss(chunkinfo)
        self.window.update_loss(chunkinfo)
        self.rtoEstimator.update_loss(chunkinfo)
        
        if kind == 4:
            log.debug("timeout, Interest=%s, out packet: %d" \
                      %(upcallInfo.Interest.name, self.window.packet_on_the_fly))
            #log.warn("%s" %(upcallInfo))
        else:
            log.warn("strange accident: kind=%s, Interest=%s" %(kind, upcallInfo.Interest.name))
        
        ##
        if self.split_fix != None and chunkinfo.retxN > 3 and chunkinfo.data_size > self.split_fix:
            t1 = chunkinfo.data_size/2
            t2 = chunkinfo.data_size - t1
            ci1 = ChunkInfo()
            ci1.beginT = chunkinfo.beginT
            ci1.begin_byte = chunkinfo.begin_byte
            temp = t1
            ci1.end_byte = ci1.begin_byte +  temp - 1
            ci1.data_size = temp
            ci1.chunk_size = temp + self.chunk_header_size
            
            ci1.packetN = math.ceil((temp + self.chunk_header_size)/float(self.packet_max_data_size))
            ci1.status = 1
            
            name = self.ndn_name
            
            name = self.ndn_name.append(ADAPTIVE_MOD_FLAG).append(str(temp)) #only leave the data size
            name = name.append(ci1.begin_byte)
            ci1.ndn_name = name
            
            ci2 = ChunkInfo()
            ci2.beginT = chunkinfo.beginT
            ci2.begin_byte = ci1.end_byte + 1
            temp = t2
            ci2.end_byte = ci2.begin_byte +  temp - 1
            ci2.data_size = temp
            ci2.chunk_size = temp + self.chunk_header_size
            
            ci2.packetN = math.ceil((temp + self.chunk_header_size)/float(self.packet_max_data_size))
            ci2.status = 1
            
            name = self.ndn_name
            
            name = self.ndn_name.append(ADAPTIVE_MOD_FLAG).append(str(temp)) #only leave the data size
            name = name.append(ci2.begin_byte)
            ci2.ndn_name = name
            
            
            self.chunkInfos.remove(chunkinfo) #list
            self.mydata.unsatisfied_chunks_keyed_by_name.pop(str(chunkinfo.ndn_name)) #orderedDic
            
            self.chunkInfos.append(ci1)
            self.mydata.unsatisfied_chunks_keyed_by_name[str(ci1.ndn_name)] = ci1
            self.chunkInfos.append(ci2)
            self.mydata.unsatisfied_chunks_keyed_by_name[str(ci2.ndn_name)] = ci2
            #self.chunkInfos.append(chunkinfo)
            #self.mydata.unsatisfied_chunks_keyed_by_name[str(name)] = chunkinfo
            log.info("chunk %s is splitted to %s and %s" %(chunkinfo.ndn_name, t1, t2))
            chunkinfo = ci1
            ci1.status = 1
            ci2.status = 0
            
        ##
        
        #window check here
        if self.window.packet_on_the_fly < self.window.get_cwnd():
            #it's already make sure that the chunk is not satisfied yet, but it could be illegal
            self.re_express_interest(chunkinfo)
        else:
            chunkinfo.status = 0 #wait for re-expressing

        
    def do_receive_content(self, kind, upcallInfo):
        """receive a contents, there are 4 different scenarios: duplicated content, in-order content, out-of-order content, illegal content
        """
        
        name = str(upcallInfo.Interest.name)
        if not name in self.mydata.unsatisfied_chunks_keyed_by_name:
            log.debug(self.mydata.unsatisfied_chunks_keyed_by_name.keys())
            #the chunkinfo is already satisfied by previous chunk (retransmission here)
            self.duplicate_content(upcallInfo)
            return
        
        
        chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name[name]
        chunkinfo.endT = datetime.datetime.now()
        chunkinfo.data_size = len(upcallInfo.ContentObject.content)
        chunkinfo.chunk_size = len(_pyndn.dump_charbuf(upcallInfo.ContentObject.ndn_data))
        chunkinfo.content = upcallInfo.ContentObject.content        
        temp = math.ceil((chunkinfo.chunk_size)/float(self.packet_max_data_size))


        self.rtoEstimator.update(chunkinfo)

        
        fbi = upcallInfo.ContentObject.signedInfo.finalBlockID 
        if  fbi != None:
            if isinstance(fbi, str):
                fbi = pyndn.Name.seg2num(fbi)

            #log.info("***************final chunk id: %s" %(fbi))
            if self.mydata.final_byte == None: #the first final block content
                self.mydata.final_byte = int(fbi)
                
            else:
                assert self.mydata.final_byte == int(fbi), "get different final block id, old %s and new %s" %(self.mydata.final_byte, int(fbi))
            
        si = upcallInfo.ContentObject.signedInfo
        if si.type == pyndn.CONTENT_NACK:
            self.nack_content(upcallInfo)
        elif si.type == pyndn.CONTENT_DATA: 
            if chunkinfo.packetN != temp:
                if self.mydata.final_byte != None and chunkinfo.end_byte > self.mydata.final_byte:#final chunk or illegal chunk
                    log.debug("final chunk, thus size is shorter than expected")
                else:
                    new_chunk_header_size = chunkinfo.chunk_size - chunkinfo.data_size
                    if self.chunk_header_size != new_chunk_header_size:
                        self.chunk_header_size = new_chunk_header_size
                        self.chunkSizeEstimator.change_chunk_header_size(self.chunk_header_size)
                        log.warn("due to header size: expected packetN (%s) != real packetN (%s), final_byte (%s), upcallInfo: %s, chunksize:%s" %(chunkinfo.packetN, temp, self.mydata.final_byte, name, chunkinfo.chunk_size))
                    else:
                        log.warn("expected packetN (%s) != real packetN (%s), final_byte (%s), upcallInfo: %s, chunksize:%s" %(chunkinfo.packetN, temp, self.mydata.final_byte, name, chunkinfo.chunk_size))
                #chunkinfo.packetN = temp
            
            self.chunkSizeEstimator.update_receiving(chunkinfo)
            
#             if self.mydata.final_byte!=None and chunkinfo.end_byte < self.mydata.final_byte:
#                 assert chunkinfo.data_size > 500, "chukinfo is strange, %s" %(chunkinfo)
#                 
            if name == self.mydata.unsatisfied_chunks_keyed_by_name.keys()[0]:
                self.in_order_content(upcallInfo)
            else:
                self.out_of_order_content(upcallInfo)
            
            retxQ = []
            for chunkinfo in self.mydata.unsatisfied_chunks_keyed_by_name.itervalues():
                if chunkinfo.status == 0:#waiting for re-expressing
                    retxQ.append(chunkinfo)
                    if len(retxQ) == 2:
                        break
            
            #here we do not check whether the request is legal or not
            for i in [0, 1]:#mulply add
                if self.window.packet_on_the_fly < self.window.get_cwnd():
                    #re-expressing is prior to request new
                    if len(retxQ) != 0:
                        chunkinfo = retxQ.pop(0)
                        chunkinfo.status = 1
                        self.re_express_interest(chunkinfo)
                        continue
                    
                    if self.mydata.final_byte== None:
                        self.first_express_interest()
                    elif self.mydata.final_byte!= None and self.mydata.next_byte < self.mydata.final_byte:
                        self.first_express_interest()
                
        else:
            log.critical("unkown Data type: %s" %(upcallInfo.ContentObject))
            
    def nack_content(self, upcallInfo):
        name = str(upcallInfo.Interest.name)
        log.info("received Nack: %s" %(name))
        chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name.pop(name)
        self.window.update_nack(chunkinfo)
        
    def duplicate_content(self, upcallInfo):
        """receive a duplicate content"""
        log.warn("received duplicated Data: %s" %(upcallInfo.Interest.name))
            
    def in_order_content(self, upcallInfo):
        """the best scenario, content is received in-order, however, we should check those buffered out-of-order chunks
        """
        name = str(upcallInfo.Interest.name)
        chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name.pop(name)
        if not self.fout.closed:
            self.fout.write(chunkinfo.content)
        else:
            log.critical("fails to write content")
        self.mydata.accept_bytes += chunkinfo.data_size
        self.mydata.accept_raw_bytes += chunkinfo.chunk_size
        
        if not self.cache_data:
            chunkinfo.content = None
        chunkinfo.status = 2 #satisfied yet
        self.mydata.satisfied_chunkN += 1
        self.mydata.expected_chunkI += 1
        self.window.update_receiving(chunkinfo)
        log.debug("received in-order Data: %s, out packet: %s" %(name, self.window.packet_on_the_fly))
        
        #check the out-of-order contents recevied before
        for name in self.mydata.unsatisfied_chunks_keyed_by_name.keys():
            chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name[name]
            if chunkinfo.endT == None:
                break
            else:
                chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name.pop(name)
                if not self.fout.closed:
                    self.fout.write(chunkinfo.content)
                else:
                    log.critical("fails to write content")
                    
                
                if not self.cache_data:
                    chunkinfo.content = None
                self.mydata.expected_chunkI += 1
                chunkinfo.status = 2 #satisfied yet
                
        
        if self.mydata.final_byte == self.mydata.accept_bytes:
            self.is_all = True
            for chunkinfo in self.mydata.unsatisfied_chunks_keyed_by_name.itervalues():
                log.warn(str(chunkinfo))
            log.warn("------------------------ %s: %s all the contents are received---------------------------" %(self.Id, self.ndn_name))
            self.stop()
        else:
            pass
            
        self._out_of_orderN = 0
                    
    def out_of_order_content(self, upcallInfo):
        """do nothing here, just buffer it and leave it to expected chunk come
        do not update the window when out-of-order, until in-order chunk is received
        """
        
        name = str(upcallInfo.Interest.name)
        chunkinfo = self.mydata.unsatisfied_chunks_keyed_by_name.get(name)
        
        self.mydata.accept_bytes += chunkinfo.data_size
        self.mydata.accept_raw_bytes += chunkinfo.chunk_size
                
        self.mydata.satisfied_chunkN += 1
        self.window.update_receiving(chunkinfo)
        
        self._out_of_orderN += 1
        if self._out_of_orderN ==4:
            #self.window.update_loss(chunkinfo)
            #self._out_of_orderN = 0
            pass
            
        log.debug("received out-of-order Data: %s, out packet: %s" %(name, self.window.packet_on_the_fly))
        
 
 
class FlowConsumerThread(FlowConsumer, threading.Thread):
    def __init__(self, Id, name, fout=None, monitor_out_dir="output", cache_data=True, enable_monitor=True, size_fix=None, size_offset=0, window_fix=None, rtt_fix=None,
                  packet_max_data_size=ETH_MTU-IP_HEADER_SIZE-UDP_HEADER_SIZE):
        threading.Thread.__init__(self)
        FlowConsumer.__init__(self, Id, name, fout=fout, monitor_out_dir=monitor_out_dir, cache_data=cache_data, enable_monitor=enable_monitor,
                              size_fix=size_fix, size_offset=size_offset, window_fix=window_fix, rtt_fix=rtt_fix, packet_max_data_size=packet_max_data_size)     
    
    
    def start(self):
        """since function start is implemented in both threading.Thread and FlowConsumer 
        """
        threading.Thread.start(self)
        
    def run(self):
        """since function start is implemented in both threading.Thread and FlowConsumer 
        """
        FlowConsumer.start(self)
    
    def stop(self):
        """in fact, stop is only implemented in FlowConsumer, but not threading.Thread, however, I just worry that future python may support stop 
        """
        #threading.Thread.stop(self)
        FlowConsumer.stop(self)
        
        return 0
        

class FlowProducer(pyndn.Closure, Controller):        
    """to build producer which can response Interest from FlowConsumer, typically, can "understand" the ADAPTIVE_FLAG 
    
    Attributes:
        ndn_name: the published ndn_name prefix, if
        path: the local path of published content(s)
        is_dir:  whether the path is a directory or not, 
            if yes, the all the files contained in the directory is published with ndn_name prefix, and files' ndn_name is append to the ndn_name prefix respectively
            if no, path is link to file and the file's ndn_name itself is ignored
        readers: use to store all the opened file reader and keyed by ndn_name 
    """
    def __init__(self, name, path, is_dir=True):
        """
        """
        Controller.__init__(self)
        
        if not name.startswith("ndnx:") and not name.startswith("/"):
            name = "/" + name
            
        self.ndn_name = pyndn.Name(name)
        
        self.path = path
        if not os.path.exists(self.path):
            log.critical("path %s does not exist" %(self.path))
            exit(0)
        if is_dir and (not os.path.isdir(self.path)):
            log.critical("path %s is not a directory" %(self.path))
            exit(0)
        if (not is_dir) and (not os.path.isfile(self.path)):
            log.critical("path %s is not a file" %(self.path))
            exit(0)
            
            
        self.handle = pyndn.NDN()
        self.is_dir = is_dir
        self.readers = {} #keyed by ndn_name

    def start(self):
        """a big different with the way, self.handle.run(-1), which cann't catch the signal interrupt all all, even if its parent thread
            however, with while loop check, the parent thread can catch the signal, for the whole process won't sink in self.handle.run()
        """
        self.status = Controller.STATUS_ON
        log.info("%s %s begin to filter Interest with ndn_name prefix: %s" %("Directory" if self.is_dir else "File", self.path, self.ndn_name))
        self.handle.setInterestFilter(self.ndn_name, self)
        
        while self.status != Controller.STATUS_OFF:
            if self.status == Controller.STATUS_ON:
                self.handle.run(DEFAULT_NDN_RUN_TIMEOUT)
            elif self.status == Controller.STATUS_STEP_ON:
                self.handle.run(DEFAULT_NDN_RUN_TIMEOUT)
                self.status = Controller.STATUS_STEP_OFF
            elif self.status == Controller.STATUS_STEP_OFF:
                time.sleep(1)
         
    def stop(self):
        self.status = Controller.STATUS_OFF
                
        self.handle.setRunTimeout(0)
        for reader in self.readers.itervalues():
            reader.close()

    #override
    def upcall(self, kind, upcallInfo):
        
        if kind != pyndn.UPCALL_INTEREST:
            log.warn("get kind: %s" %str(kind))
            return pyndn.RESULT_OK
        
        co = self.prepare(upcallInfo)
#         try:
#             co = self.prepare(upcallInfo)
#         except:
#             thetype, value, traceback = sys.exc_info()
#             log.error("get exception: %s, %s, %s" %(thetype, value, traceback))
#             co = None
            
        if co == None:
            log.warn("co == None")
            pass
        else:
            rst = self.handle.put(co)
            if rst < 0:
                log.warn("fail put content: %s, result: %s" %(co.ndn_name, rst))
            else:
                pass
            #("content: %s" %(co.ndn_name))
            
            
        return pyndn.RESULT_INTEREST_CONSUMED
    
    def prepare(self, upcallInfo):
        ist = upcallInfo.Interest
        ist_name = ist.name
        
        flag_index = None #len(ist_name) - 2 #index of the end component
        
        for i in range(len(ist_name)-2):
            sub = ist_name[i]
            if sub == ADAPTIVE_MOD_FLAG:
                flag_index = i
                break
        
        if flag_index == None:
            log.error("not a flow consumer's interest, ignore: %s" %(ist_name))
            return None
        
        expected_data_size = int(ist_name[flag_index+1])
        begin_byte = int(ist_name[flag_index+2])
        name = ist_name[:flag_index] #not include the flag
        
        
        name_str = str(name)
        
        if name_str in self.readers:
            reader = self.readers[name_str]
        else:
            if self.is_dir:
                subpath = ist_name[upcallInfo.matchedComps:flag_index]
                fpath = self.path
                for i in range(upcallInfo.matchedComps, flag_index):
                    temp = ist_name[i]
                    fpath = os.path.join(fpath, temp)
                #assume that matchedComps is the number of matched components, not index
                
                if not os.path.exists(fpath):
                    log.critical("path %s from Interest %s does not exist" %(fpath, ist_name))
                    return None
                if os.path.isdir(fpath):
                    log.critical("path %s from Interest %s is not a file" %(fpath, ist_name))
                    return None
                
            else:#not serve all the directory
                if upcallInfo.matchedComps != flag_index:
                    log.critical("umatched ndn_name: %s, %s"%(ist_name, self.ndn_name))
                    return None
                else:
                    fpath = self.path
                    
            reader = Reader(fpath=fpath)
            self.readers[name_str] = reader
        
        data = reader.read(begin_byte, expected_data_size)
        
        if data == None:
            log.critical("Interest %s: begin_byte %s > file_size %s" %(ist_name, begin_byte, reader.fsize))
            nack = self._nack_template(ist_name, reader)
            return nack
        else:
            log.info("Interest: %s, expected_data_size: %s, begin_byte: %s, data_size: %s" \
                      %(ist.name, expected_data_size, begin_byte, len(data)))
                        
            co = self._data_template(ist_name, data, reader.fsize, pyndn.CONTENT_DATA)
            
            return co
    
    def _nack_template(self, name, reader):
        nack = self._data_template(name, None, final_byte=reader.fsize, si_type=pyndn.CONTENT_NACK)
        return nack
    
    def _data_template(self, name, data, final_byte, si_type=pyndn.CONTENT_DATA):
        # create a new data packet
        co = pyndn.ContentObject()

        # since they want us to use versions and segments append those to our ndn_name
        #co.name = self.ndn_name.appendVersion().appendSegment(0)
        co.name = name
        
        # place the content
        co.content = data

        si = co.signedInfo

        key = self.handle.getDefaultKey()
        # key used to sign data (required by ndnx)
        si.publisherPublicKeyDigest = key.publicKeyID

        # how to obtain the key (required by ndn); here we attach the
        # key to the data (not too secure), we could also provide ndn_name
        # of the key under which it is stored in DER format
        si.freshnessSeconds = 1
        si.keyLocator = None
        si.keyLocator = pyndn.KeyLocator(key)

        # data type (not needed, since DATA is the default)
        
        si.type = si_type
        if final_byte != None:
            si.finalBlockID = pyndn.Name.num2seg(final_byte)
    
        
        co.sign(key)
        return co
        
class Reader(object):
    def __init__(self, fpath):
        self.fpath = fpath
        fd = open(fpath)
        fsize = os.path.getsize(fpath)
        self.fd = fd
        self.fsize = fsize
    
    def read(self, begin_byte, data_size):
        if self.fd.closed:
            self.fd = open(fpath)
            
        if begin_byte >= self.fsize:
            return None
        
        if self.fd.tell() != begin_byte:
            log.debug("move to %s" %(begin_byte))
            self.fd.seek(begin_byte)
                
        data = self.fd.read(data_size)
        
        return data
    
    
    def close(self):
        if not self.fd.closed:
            self.fd.close()
        
