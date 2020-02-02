#!/usr/bin/env python

# Vision Widget - OpenCV widget for LinuxPNP
#
# Based on CamView, Copyright (c) 2016 Norbert Schechner
# Based on the DisplayImage code from Jay Rambhia 
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import cv2 as cv
import gtk
import gobject 
import threading
import subprocess
import time
import hal
import numpy as np
import re

gtk.gdk.threads_init()

# prepared for localization
import gettext
_ = gettext.gettext

# check if opencv3 is used, so we will have to change attribut naming
from pkg_resources import parse_version
OPCV3 = parse_version(cv.__version__) >= parse_version('3')

mmpp = 1
FPS = 0
mirror = 1

def horzRect(rect):
	if rect[1][0] < rect[1][1]:
		return [ rect[0], [rect[1], rect[0]], rect[2] + 90 ]
	return rect

def similarSize(v1, v2, sdif):
	w1 = max(v1[0], v1[1])
	h1 = min(v1[0], v1[1])
	w2 = max(v2[0], v2[1])
	h2 = min(v2[0], v2[1])
	r = (abs(w1 - w2) < sdif*w1+3) and (abs(h1 - h2) < sdif*h1+3)
#	print "r={} {}<{} {}<{}".format(r, abs(w1 - w2), sdif*w1, abs(h1 - h2), sdif*h1)
	return r

def rectOffs(frame, rect):
	global mmpp
	x = (rect[0][0]-frame.shape[1]/2)*mmpp
	y = (rect[0][1]-frame.shape[0]/2)*mmpp
	w = rect[1][0]*mmpp
	h = rect[1][1]*mmpp
	a = rect[2]
	return [[x, y], [w, h], a]

def drawRect(frame, rect, clr, sizeOnly=False):
	global mmpp
	box = np.int0(cv.boxPoints(rect))
	cv.drawContours(frame, [box], -1, clr, 2)
	cv.circle(frame, tuple(np.int0(rect[0])), 3, clr, -1)
	((x, y), (w, h), a) = rectOffs(frame, rect)
	if sizeOnly:
		t = "%.02fx%.02f" % (w, h)
	else:
		t = "%+.2f %+.2f %+03.1f (%.02fx%.02f)" % (x, y, a, w, h)

	(s, b) = cv.getTextSize(t, cv.FONT_HERSHEY_SIMPLEX, 0.4, 1)
	tx = int(rect[0][0] - s[0]/2)
	bb = cv.boundingRect(box)
	ty = int(rect[0][1] - bb[3]/2 - 8)
	cv.putText(frame, t, (tx, ty), cv.FONT_HERSHEY_SIMPLEX, 0.4, clr, 1)

#	cv.putText(frame, "%.02f x %.02f" % (rect[1][0]*mmpp,rect[1][1]*mmpp), , cv.FONT_HERSHEY_SIMPLEX, 0.5, clr, 1)

def skew(a):
	while a > 45: a -= 90
	while a < -45: a += 90
	return a

#
#
#

#; code			roi	thresh	pin		bbox		  part
# 600008		250	120     0.27,0.35	3.74,5.50	; SO8
#-600008		250	170     0.55,0.35	3.95,5.80	; SO8*

class VPart:
	def __init__(self, l):
		s = re.sub(r'\s*;.*', '', l)	# remove comments
		try:
			(code, roi, th, pin, box) = s.split()
			self.code = float(code)
			self.roi = int(roi)
			self.th = int(th)
			self.pinSize = [float(v) for v in pin.split(',')]
			self.ellipse = False
			if box == '-':
				self.boxSize = [0, 0]
			else:
				self.boxSize = [float(v) for v in box.split(',')]
				if len(self.boxSize) == 2:
					self.ellipse = True
				else:
					self.ellipse = False
			if self.code >= 0: self.cam = 0
			else: self.cam = 1
		except ValueError as e:
			raise e

class VCfg:
	def __init__(self, name):
		self.name = name
		self.part = {}

	def reload(self):
		self.part = {}
		for l in open(self.name, "r"):
			try:
				p = VPart(l)
				self.part[p.code] = p
			except ValueError as e:
				pass
		print 'cfg reloaded'

	def get(self, k):
		try:
			return self.part[k]
		except KeyError:
			return VPart("0 0 0 0,0 0,0")

from collections import deque

class RectList:
	def __init__(self, n):
		self.l = deque()
		self.n = n

	def clear(self):
		self.l.clear()

	def append(self, a):
		self.l.append(a)
		while(len(self.l) > self.n):
			self.l.popleft()

	def isstable(self, d, t):
		if len(self.l) < self.n: return False
		x = [r[0][0] for r in self.l]
		y = [r[0][1] for r in self.l]
		a = [r[2] for r in self.l]
		if max(x) - min(x) > d: return False
		if max(y) - min(y) > d: return False
		if max(a) - min(a) > t: return False
		return True

#
#
#

class Vision(gtk.VBox):
    
	'''
   
	GladeVcp Widget - CamView widget, showing the live stream
	                 from a web cam or other connected cameras.

	Prerequities : 
	install opencv (cv), min version 2.3 requiered!
	on Whessy and Jessie just do : 
	apt-get install python-opencv
	Will install also some depencies
    
	on Ubuntu 10.04 you will have to build from source
	see: http://docs.opencv.org/2.4/doc/tutorials/introduction/linux-install.html
   
	your camera must be recognised by v4l2, to test that I do recommend to install qv4l2
	apt-get install qv4l2
	start from terminal with qv4l2
	you can use this tool to get a live stream, you are on the right way.
    
	please make sure you have v4l2-ctl installed it will be used to get your devices
	sudo apt-get install v4l-utils
    
	To be able to open the camera settings from the App, you have to install also v4l2ucp
	sudo apt-get install v4l2ucp
    
	if you want special setting of your camera on start up, you can supply a command through the properties
	something like this:
	v4l2-ctl -d /dev/video1 -c exposure_auto=1 -c exposure_auto_priority=0 -c exposure_absolute=10
	it sets for your second camera (/dev/video1), the shutter time to manual settings and changes the shutter time to 10 ms.
	see v4l2-ctl --help for more details
    
	v4l2-ctl --list-formats-ext
	will list all supported frame sizes and frame rates for your camera
    
	'''
	__gtype_name__ = 'Vision'
	__gproperties__ = {
	}
	__gproperties = __gproperties__

	__gsignals__ = {
		'clicked': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)),
		'exit': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
	}



	def __init__(self):
		super(Vision, self).__init__()

		self.__version__ = "0.1.2"

		# set other default values or initialize them
		self.color =(0, 255, 255)
		self.linewidth = 1
		self.img_gtk = None
		self.paused = False
		self.thrd = None
		self.initialized = False

		self.rl = RectList(3)

		self.hal = hal.component("cv")
		self.hal.newpin("enable", hal.HAL_BIT, hal.HAL_IN)
		self.hal.newpin("success", hal.HAL_BIT, hal.HAL_OUT)
		self.hal.newpin("part", hal.HAL_FLOAT, hal.HAL_IN)
		self.hal.newpin("rc", hal.HAL_FLOAT, hal.HAL_OUT)
		self.hal.newpin("dx", hal.HAL_FLOAT, hal.HAL_OUT)
		self.hal.newpin("dy", hal.HAL_FLOAT, hal.HAL_OUT)
		self.hal.newpin("a", hal.HAL_FLOAT, hal.HAL_OUT)
		self.hal.newpin("debug", hal.HAL_FLOAT, hal.HAL_IN)
		self.hal.newpin("reload", hal.HAL_BIT, hal.HAL_IO)
		self.hal.newpin("pp", hal.HAL_FLOAT, hal.HAL_IN)
		self.hal.newpin("grid", hal.HAL_FLOAT, hal.HAL_IN)
		self.hal.newpin("z", hal.HAL_FLOAT, hal.HAL_IN)
		self.hal.newpin("h", hal.HAL_FLOAT, hal.HAL_IN)

		self.hal.newpin("jog-x", hal.HAL_S32, hal.HAL_OUT)
		self.hal.newpin("jog-y", hal.HAL_S32, hal.HAL_OUT)
		self.hal.newpin("jog-scale", hal.HAL_FLOAT, hal.HAL_OUT)
		self.hal.newpin("jog-enable", hal.HAL_BIT, hal.HAL_OUT)

		self.hal.ready()

		self.cfg = VCfg('vision.cfg')
		self.cfg.reload()

		self.old_frames = 0

		# set the correct camera as video device
		self.cam = ( cv.VideoCapture(2), cv.VideoCapture(0) )

		# 0  = CAP_PROP_POS_MSEC        Current position of the video file in milliseconds.
		# 1  = CAP_PROP_POS_FRAMES      0-based index of the frame to be decoded/captured next.
		# 2  = CAP_PROP_POS_AVI_RATIO   Relative position of the video file
		# 3  = CAP_PROP_FRAME_WIDTH     Width of the frames in the video stream.
		# 4  = CAP_PROP_FRAME_HEIGHT    Height of the frames in the video stream.
		# 5  = CAP_PROP_FPS             Frame rate.
		# 6  = CAP_PROP_FOURCC          4-character code of codec.
		# 7  = CAP_PROP_FRAME_COUNT     Number of frames in the video file.
		# 8  = CAP_PROP_FORMAT          Format of the Mat objects returned by retrieve() .
		# 9  = CAP_PROP_MODE            Backend-specific value indicating the current capture mode.
		# 10 = CAP_PROP_BRIGHTNESS      Brightness of the image (only for cameras).
		# 11 = CAP_PROP_CONTRAST        Contrast of the image (only for cameras).
		# 12 = CAP_PROP_SATURATION      Saturation of the image (only for cameras).
		# 13 = CAP_PROP_HUE             Hue of the image (only for cameras).
		# 14 = CAP_PROP_GAIN            Gain of the image (only for cameras).
		# 15 = CAP_PROP_EXPOSURE        Exposure (only for cameras).
		# 16 = CAP_PROP_CONVERT_RGB     Boolean flags indicating whether images should be converted to RGB.
		# 17 = CAP_PROP_WHITE_BALANCE   Currently unsupported
		# 18 = CAP_PROP_RECTIFICATION   Rectification flag for stereo cameras 
		#                               (note: only supported by DC1394 v 2.x backend currently)     
		self.cam[0].set(cv.CAP_PROP_FRAME_WIDTH, 1280)
		self.cam[0].set(cv.CAP_PROP_FRAME_HEIGHT, 1024)
		self.cam[0].set(cv.CAP_PROP_BUFFERSIZE, 1);
		self.cam[1].set(cv.CAP_PROP_FRAME_WIDTH, 1280)
		self.cam[1].set(cv.CAP_PROP_FRAME_HEIGHT, 1024)
		self.cam[1].set(cv.CAP_PROP_BUFFERSIZE, 1);
		
		# make the main GUI
		self.image_box = gtk.EventBox()
		self.add(self.image_box)
		self.img_gtk = gtk.Image()
		self.image_box.add(self.img_gtk)
		# self.image_box.connect("size-allocate", self._on_size_allocate)
		self.image_box.connect("destroy", self.quit)

		self.image_box.connect("button-press-event", self.on_click)
	        self.image_box.connect("button-release-event", self.on_release)
        	self.image_box.connect("motion-notify-event", self.on_mousemove)
		self.drag = 0
		self.drag_x = 0
		self.drag_y = 0

		self.initialized = True
		self.thread_gtk()
		gobject.timeout_add( 2000, self._periodic )

	def on_click(self, widget, event):
		global mmpp, mirror
		self.drag = mirror
		self.drag_x = -event.x*self.drag - self.hal["jog-x"]
		self.drag_y = event.y*self.drag - self.hal["jog-y"]
		self.hal["jog-scale"] = mmpp
		self.hal["jog-enable"] = True
		print("down")

	def on_release(self, widget, event):
		self.drag = 0
		self.hal["jog-enable"] = False
		print("up")

	def on_mousemove(self,widget,event):
		if self.drag != 0:
			self.hal["jog-x"] = -event.x*self.drag - self.drag_x
			self.hal["jog-y"] = event.y*self.drag - self.drag_y
			print(self.hal["jog-x"], self.hal["jog-y"])

	def thread_gtk(self):
		# without this threading function camera speed was realy poor
		self.condition = threading.Condition()
		self.thrd = threading.Thread(target = self.run, name = "Vision thread")
		self.thrd.daemon = True
		self.thrd.start()

	def _periodic(self):
		global FPS
		FPS = (self.captured_frames - self.old_frames)/2.0
		if FPS < 0: FPS = 0
		self.old_frames = self.captured_frames
		#self.lbl_frames.set_text("FPS\n" + str(FPS) )

		if self.hal.reload:
			self.cfg.reload()
			self.hal.reload = False

		return True

	def averageCenter(self, rect, cam):
		if not self.hal.success:
			r = (rect[0], rect[1], skew(rect[2]))
			print "%.3f %.3f %.2f" % (r[0][0], r[0][1], r[2])
			self.rl.append(r)
			if self.rl.isstable(0.03, 0.15):
				self.hal.dx = rect[0][0]
				self.hal.dy = rect[0][1]
				self.hal.a = skew(rect[2])
				self.hal.rc = self.hal.part
				self.hal.success = True
				print "***"

	def run(self):
		global mmpp, mirror
		self.captured_frames = 0
		while True:
			try:
				##################################
				p = self.cfg.get(self.hal.part)
				##################################

				if p.cam == 0:
					# top camera
					result, frame = self.cam[0].read()
					if not result: continue

					frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
					frame = cv.flip(frame, -1)
#					mmpp = 0.01612	# mm /pixel @ 1280x1024
					mmpp = 0.0167	# mm /pixel @ 1280x1024
					mirror = 1
				else:
					# bottom camera
					result, frame = self.cam[1].read()
					if not result: continue

					frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
					frame = cv.flip(frame, 1)
					#mmpp = 0.025	# mm /pixel @ 1280x1024
					mmpp = 0.03 - (abs(self.hal.z)-8.1 + self.hal.h-1.5)/13*0.01
					mirror = -1

					src = np.array([
						[0,0], [1279,0],
						[1279, 1023], [0, 1023]
						], dtype = "float32")

					dst = np.array([
						[1,-11], [1279,-5-4],
						[1279+17, 1023+8+4], [-25, 1023+6]
						], dtype = "float32")

					M = cv.getPerspectiveTransform(src, dst)
					frame = cv.warpPerspective(frame, M, (1280, 1024))

      				fx = int(frame.shape[1]/2)	# center
				fy = int(frame.shape[0]/2)
				s = max(320, p.roi)
				frame = frame[fy-s:fy+s, fx-s:fx+s]	# crop camera frame
        
				if not self.hal.enable:
					self.hal.success = False
					self.rl.clear()
#				elif self.hal.success or (roi < 1):
				elif p.roi < 1:
					pass
				else:
					# enter of the image
					icx = int(frame.shape[1]/2)
					icy = int(frame.shape[0]/2)
					gray = frame[icy-p.roi:icy+p.roi, icx-p.roi:icx+p.roi]
					gray = cv.cvtColor(gray, cv.COLOR_BGR2GRAY)
					gray = cv.GaussianBlur(gray, (3, 3), 0)
        
					if p.th > 0:
						gray = cv.threshold(gray, p.th, 255, cv.THRESH_BINARY)[1]
					else:
						gray = cv.threshold(gray, -p.th, 255, cv.THRESH_BINARY_INV)[1]
        
					if int(self.hal.debug) & 1:	# display b&w image for debug
						frame[icy-p.roi:icy+p.roi, icx-p.roi:icx+p.roi] = cv.cvtColor(gray, cv.COLOR_GRAY2RGB)

					cnts = cv.findContours(gray.copy(), cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE, offset=(icx-p.roi, icy-p.roi))
					# cnts = cv.findContours(gray.copy(), cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE, offset=(icx-p.roi, icy-p.roi))
					# cnts = cnts[0] if imutils.is_cv() else cnts[1]

					points = []
					pinSize = (p.pinSize[0] / mmpp, p.pinSize[1] / mmpp)
					if len(p.pinSize) > 2:
						pin2Size = (p.pinSize[2] / mmpp, p.pinSize[3] / mmpp)
					else:
						pin2Size = (0, 0)
					boxSize = (p.boxSize[0] / mmpp, p.boxSize[1] / mmpp)
					        
					for cnt in cnts[1]:
						# print c	# [[[1 1] [2 2] [3 3]]]
						# [[cx cy] [w h] a]
						if p.ellipse:
							if len(cnt) < 5: continue
							rect = cv.fitEllipse(cnt)
						else:
							if len(cnt) < 4: continue
							epsilon = 0.1 * cv.arcLength(cnt, True)
							poly = cv.approxPolyDP(cnt, epsilon, True)
							rect = cv.minAreaRect(cnt)
						if pin2Size[0] > 0 and (similarSize(pinSize, rect[1], 0.25) or similarSize(pin2Size, rect[1], 0.25)):
							if boxSize[0] > 0:
								for i in cnt.tolist():
									points.append(i[0])
#								points.append([rect[0][0], rect[0][1]+rect[1][1]/2])
#								points.append([rect[0][0], rect[0][1]-rect[1][1]/2])
								drawRect(frame, rect, (0, 50, 255), True)
							else:
								self.averageCenter(rectOffs(frame, rect), p.cam)							
								if self.hal.success:
									drawRect(frame, rect, (0, 255, 0))
								else:
									drawRect(frame, rect, (200, 255, 0))
								break
						elif similarSize(pinSize, rect[1], 0.25):
							if boxSize[0] > 0:	# multipin
								points.append(rect[0])
								#points.append([rect[0][0], rect[0][1]+rect[1][1]/2])
								#points.append([rect[0][0], rect[0][1]-rect[1][1]/2])
								drawRect(frame, rect, (0, 50, 255), True)
							else:
								self.averageCenter(rectOffs(frame, rect), p.cam)
								if self.hal.success:
									drawRect(frame, rect, (0, 255, 0))
								else:
									drawRect(frame, rect, (200, 255, 0))
								break
						elif (int(self.hal.debug) & 4) and similarSize(pinSize, rect[1], 0.5):
							drawRect(frame, rect, (255, 0, 0), True)
						elif int(self.hal.debug) & 8:
							drawRect(frame, rect, (255, 0, 0), True)
						if int(self.hal.debug) & 16:
							cv.drawContours(frame, cnt, -1, (255,0,0), 2)

					if boxSize[0] > 0:
						p10 = [(v[0]*10,v[1]*10) for v in points]
						r10 = cv.minAreaRect(np.array(p10).reshape((-1,1,2)).astype(np.int32))
						rect = ((r10[0][0] / 10.0, r10[0][1] / 10.0), (r10[1][0] / 10.0, r10[1][1] / 10.0), r10[2])
						if similarSize(boxSize, rect[1], 0.05) and abs(skew(rect[2])) < 8:
							self.averageCenter(rectOffs(frame, rect), p.cam)
							if self.hal.success:
								# drawRect(frame, ((int(self.dx/mmpp)+frame.shape[1]/2, int(self.dy/mmpp)+frame.shape[0]/2), rect[1], rect[2]), (0, 255, 0))
								drawRect(frame, ((int(self.hal.dx/mmpp)+frame.shape[1]/2, int(self.hal.dy/mmpp)+frame.shape[0]/2), rect[1], rect[2]), (0, 255, 0))
							else:
								drawRect(frame, rect, (200, 200, 0))
								# print points
						elif int(self.hal.debug) & 2: # and (abs(w - pw) < 0.5*pw) and (abs(h - ph) < 0.5*ph):
#							drawRect(frame, (rect[0], rect[1], skew(rect[2])), (255, 0, 0))
							drawRect(frame, rect, (255, 0, 0))

				##############################

				frame = self._draw_lines(frame)
				fx = int(frame.shape[1]/2)	# center
				fy = int(frame.shape[0]/2)
				#frame = frame[fy-320:fy+320, fx-320:fx+320]	# crop
				frame = cv.resize(frame, (640, 640))

				t = ''
				if self.hal.enable: t += "PART:{} CAM{} ".format(p.code, p.cam)
				if self.hal.grid != 0: t += "G:{} ".format(self.hal.grid)
				t += "FPS:{0:.1f} ".format(FPS)
				t = t.rstrip()

				if t != '':
					(s, b) = cv.getTextSize(t, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)
					cv.rectangle(frame, (10-5, 20-s[1]-3), (10+s[0]+5, 24), (0, 0, 0, 100), -1)
					cv.putText(frame, t, (10, 20), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv.LINE_AA)

				self.show_image(frame)
				#time.sleep(0.01)
				# we put that in a try, to avoid an error if the user 
				# use the App 24/7 and get to large numbers
				try:
					self.captured_frames += 1
				except:
					self.captured_frames = 0
        
			except KeyboardInterrupt:
				print "got SIGINT"
#				selt.hal.exit()
#				self.quit()
				break

	def _draw_lines(self, frame):
		h = frame.shape[0]
		w = frame.shape[1]
		pt1 = (0, int(h/2))
		pt2 = (w, int(h/2))
		cv.line(frame, pt1, pt2, self.color, 1)
		pt1 = (int(w/2), 0)
		pt2 = (int(w/2), h)
		cv.line(frame, pt1, pt2, self.color, 1)

		if self.hal.grid < 0.1: return frame

		if self.hal.pp == 0:
			pp = mmpp
		else:
			pp = self.hal.pp
		l = 5
		o = int(w/2*pp/self.hal.grid)*self.hal.grid
		i = -o
		while i <= o:
			x = int(i/pp + w/2)+1
			y = int(i/pp + h/2)+1
			cv.line(frame, (x, int(h/2)-l), (x, int(h/2)+l), self.color, 1)
			cv.line(frame, (int(w/2)-l, y), (int(w/2)+l, y), self.color, 1)
			i += self.hal.grid
		return frame

	def _draw_text(self, frame):
#		cv.putText(frame, _("Radius = {}".format(self.radius)), 
#			(10, 20), cv.FONT_HERSHEY_SIMPLEX, 0.5, self.color, 1)
#		cv.putText(frame, _("Circles = {}".format(self.circles)), 
#			(10, 40), cv.FONT_HERSHEY_SIMPLEX, 0.5, self.color, 1)
		return frame

	def show_image(self, frame):
		self.img_pixbuf = gtk.gdk.pixbuf_new_from_array(frame, gtk.gdk.COLORSPACE_RGB, 8)
		self.img_gtk.set_from_pixbuf(self.img_pixbuf)
		self.img_gtk.show()
		self.show_all()

	def quit(self, data = None):
		if not self.paused:
			print "quit"
			self.paused = True
			self.cam[0].release()
			self.cam[1].release()
			cv.destroyAllWindows()
			self.destroy()
			v.hal.exit()
			# gtk.main_quit()

if __name__ == '__main__':
	window = gtk.Window(gtk.WINDOW_TOPLEVEL)
	window.set_title("Vision")
	v = Vision()
	window.add(v)
	window.show_all()
	window.connect("destroy", v.quit)
	try:
		gtk.main()
	except KeyboardInterrupt:
		print "main got SIGINT"
		window.destroy()
 
