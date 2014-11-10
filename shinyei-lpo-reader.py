import os 
import sys, time, syslog
from datetime import datetime, timedelta
import commands
import subprocess
import json
import httplib, urllib


class ShinyeiLpoReader:

	def __init__(self, sensorId, gpio):
		self.id=sensorId
		self.gpio = gpio
		self.openGpio()

	def openGpio(self):
		pinModePath = os.path.join(os.path.normpath('/sys/devices/virtual/misc/gpio/mode/'), self.gpio)
		file = open(pinModePath, 'r+')
		file.write("0")
		file.close()

		pinValuePath = os.path.join(os.path.normpath('/sys/devices/virtual/misc/gpio/pin/'), self.gpio)
		self.gpioFile = open(pinValuePath, 'r')


	def pulse(self,value):
		t = time.time()
		if self.ltime!=0:
			dtime = t-self.ltime
			self.lpotime[value] += dtime
			duration = int(dtime*1000);
#			print("   #{0} -> {1} ms".format(1-value,duration))
#		else:
#			print("   #{0} -> starting".format(1-value))
		self.ltime=t


	def read( self, duration ):
		count = 0
		while count < 10:
			low = 0
			high = 0
			start = os.times()[4]

			self.ltime = 0
			self.lpotime = [0,0]
			lvalue = -1
			lasttime = start

			while os.times()[4]<start+duration:
				time.sleep(1.0/1000.0)
				self.gpioFile.seek(0)
				value = int(self.gpioFile.read())

				if lvalue != value:
					self.pulse(value)
					lvalue = value

				low = int(self.lpotime[1]*1000)
				high = int(self.lpotime[0]*1000)
				if (low+high!=0):
					ratio = float(low) / (low+high)
				else:
					ratio = -1

				ctime = os.times()[4]
				if ctime>lasttime+5:
					lasttime = ctime
					print ("{0}: {1} {2}+{3}={4}\033[0m".format(time.strftime("%H:%M:%S"),ratio*100,low,high,low+high))

			return ratio


	def post(self,value):
		try:
			idata = dict( value=value, type='shinyei', unit='lpo' )
			params = urllib.urlencode(dict(postdata=dict( id=self.id, time=datetime.now().isoformat(), data = idata )))                
			headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
			conn = httplib.HTTPConnection("sensor.aqicn.org")
			conn.request("POST", "/sensor/upload/", params, headers)
			response = conn.getresponse()
			print("Posting "+str(idata)+" -> {0} {1} ".format(response.status, response.reason))
			data = response.read()
			conn.close()
			data= json.loads(data)
			print(data)
			return data["result"] == "ok"

		except ValueError:  # includes simplejson.decoder.JSONDecodeError
			print("Data decoding error for "+data)
			return 0


def loop():
	reader = ShinyeiLpoReader("shinyei.test-sensor","gpio7")
	while 1:
		ratio = reader.read(60)
		print ("{0}: {1} ---".format(time.strftime("%H:%M:%S"),ratio))
		reader.post(ratio);

if __name__ == "__main__":
	loop()


