1.
the tool reply on NDNx, pyndn, and gst(0.10)
set up NDNx, pyndn: http://www.douban.com/note/309738944/
install gst: http://www.douban.com/note/311921965/
set up development: http://www.douban.com/note/312254368/

note about gst: http://www.douban.com/note/311921965/
2.
The most important files are ndn_flow.py, nplayer.py
ndn_flow.py provides the flow transmission APIs
nplayer.py call APIs from ndn_flow and get the data from producer, then put it in gst to process

other python files are used for testing for trial

3.

currently, we support 
python gui.py [-m] [-f]

4.
for test, we provide a media server which runs data producer (FlowProducer) paired with ndn_flow (FlowProducer),
add one entry to FIB of NDNx, run command:
    ndndc add ndn:/h243 udp 202.112.49.243 6363
which connect to 202.112.49.243


5.
gst-launch-0.10 playbin2 uri=b1.mp4



for audio
gst-launch filesrc location=b1.mp4 ! qtdemux name=demuxer demuxer. ! queue ! faad ! audioconvert ! audioresample ! autoaudiosink demuxer. ! queue ! ffdec_h264 ! ffmpegcolorspace ! autovideosink 2
x.
DEBUG Info.
1) "_pyndn.NDNError: Unable to connect with NDN daemon: No such file or directory [2]", the host have to run ndnd with shell command: ndndstart


----------------
Xiaoke (Shock) Jiang <shock.jiang@gmail.com>
last revisited on Oct 24, 2013


svn up -r 78 get the relase-0.1
svn co svn://202.112.49.243:8768 nplayer