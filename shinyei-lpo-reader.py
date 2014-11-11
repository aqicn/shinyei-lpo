import os 
import sys, time, syslog
from datetime import datetime, timedelta
import commands
import subprocess
import json
import httplib, urllib


class LpoReader:

	def __init__(self):
		self.start()

	def start( self ):
		self.ltime = 0
		self.lvalue = -1
		self.lpotime = [0,0]
		self.count = 0

	def read( self, value ):

		if self.lvalue != value:
			t = time.time()
			if self.ltime!=0:
				dtime = t-self.ltime
				self.lpotime[self.lvalue] += dtime
			self.ltime=t
			self.lvalue = value
			if value==0:
				self.count += 1

	def getcount( self ):
		return self.count

	def ratio( self ):
		low  = self.lpotime[0]
		high = self.lpotime[1]

		if self.ltime!=0:
			dt = time.time()-self.ltime
			if self.lvalue==0:
				low += dt
			else:
				high += dt

		if (low+high!=0):
			ratio = float(low) / (low+high)
		else:
			ratio = -1

		return ratio	

class ShinyeiLpoReader:

	def __init__(self, gpio1, gpio2):
		self.gpio1 = self.openGpio(gpio1)
		self.gpio2 = self.openGpio(gpio2)
		self.lpo1 = LpoReader()
		self.lpo2 = LpoReader()

	def openGpio(self,gpio):
		pinModePath = os.path.join(os.path.normpath('/sys/devices/virtual/misc/gpio/mode/'), gpio)
		file = open(pinModePath, 'r+')
		file.write("0")
		file.close()

		pinValuePath = os.path.join(os.path.normpath('/sys/devices/virtual/misc/gpio/pin/'), gpio)
		gpioFile = open(pinValuePath, 'r')
		return gpioFile



	def read( self, duration ):
		start = os.times()[4]

		lasttime = start
		self.lpo1.start()
		self.lpo2.start()

		while os.times()[4]<start+duration:
			time.sleep(1.0/1000.0)

			self.gpio1.seek(0)
			value = int(self.gpio1.read())
			self.lpo1.read(value)

			self.gpio2.seek(0)
			value = int(self.gpio2.read())
			self.lpo2.read(value)

			ctime = os.times()[4]
			if ctime>lasttime+5:
				lasttime = ctime
				ratio1 = round(self.lpo1.ratio()*10000)/100
				ratio2 = round(self.lpo2.ratio()*10000)/100
				print ("{0}: {1}({3}) {2}({4})".format(time.strftime("%H:%M:%S"),ratio1,ratio2,self.lpo1.getcount(),self.lpo2.getcount()))

		return [self.lpo1.ratio(),self.lpo2.ratio()]


class AqicnUploader:

	def __init__(self, sensorId):
		self.id=sensorId

	def post(self,values):
		try:
			idat1= dict( value=value, type='shinyei-pdp42ns-1u', unit='lpo' )
			idat2= dict( value=value, type='shinyei-pdp42ns-2.5u', unit='lpo' )
			params = urllib.urlencode(dict(postdata=dict( id=self.id, time=datetime.now().isoformat(), data = [idat1,idat2])))
			headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
			conn = httplib.HTTPConnection("sensor.aqicn.org")
			conn.request("POST", "/sensor/upload/", params, headers)
			response = conn.getresponse()
			print("Posting "+str(idat1)+" "+str(idat2)+" -> {0} {1} ".format(response.status, response.reason))
			data = response.read()
			conn.close()
			data= json.loads(data)
			print("Sever says "+str(data))
			return data["result"] == "ok"

		except ValueError:  # includes simplejson.decoder.JSONDecodeError
			print("Data decoding error for "+data)
			return 0


def loop():
	reader = ShinyeiLpoReader("gpio7","gpio6")
	uploader = AqicnUploader("shinyei.test-sensor")
	while 1:
		ratio = reader.read(60)
		print ("--- {0} --- {1} {1} ---".format(time.strftime("%H:%M:%S"),ratio[0],ratio[1]))
		uploader.post(ratio);

if __name__ == "__main__":
	loop()


