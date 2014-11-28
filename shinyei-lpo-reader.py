import os 
import sys, time
from datetime import datetime, timedelta
import commands
import subprocess
import json
import httplib, urllib
import tempfile
import pickle


class LpoReader:

	def __init__(self):
		self.start()

	def start( self ):
		self.ltime = 0
		self.lvalue = -1
		self.lpotime = [0,0]
		self.count=0

	def read( self, value ):

		if self.lvalue != value:
			t = time.time()
			if self.ltime!=0:
				dtime = t-self.ltime
				self.lpotime[self.lvalue] += dtime
			self.ltime=t
			self.lvalue = value
			if value==0:
				self.count+=1


	def ratio( self ):
		low = self.lpotime[0]
		high = self.lpotime[1]

		if self.ltime!=0:
			dt =  time.time()-self.ltime
			if self.lvalue==0:
				low += dt
			else:
				high += dt

		if (low+high!=0):
			ratio = float(low) / (low+high)
		else:
			ratio = -1

		return ratio	

	def getcount( self ):
		return self.count


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
			if ctime>lasttime+6:
				lasttime = ctime
				ratio1 = round(self.lpo1.ratio()*10000)/100
				ratio2 = round(self.lpo2.ratio()*10000)/100
				print ("{0}: {1}({3}) {2}({4})".format(time.strftime("%H:%M:%S"),ratio1,ratio2,self.lpo1.getcount(),self.lpo2.getcount()))



		return [self.lpo1.ratio(),self.lpo2.ratio()]


class SensorDataUploader:

	def __init__(self, id):
		self.faildate = 0
		self.writecnt = 0
		self.id = id

	def httpPost(self,idata):
		try:
			params = urllib.urlencode(dict(postdata=dict( id=self.id, data = idata )))
			headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
			conn = httplib.HTTPConnection("sensor.aqicn.org")
			conn.request("POST", "/sensor/upload/", params, headers)
			response = conn.getresponse()
			data = response.read()
			print("Posting {2} -> {0} {1} ".format(response.status, response.reason,idata))
			conn.close()
			djson = json.loads(data)
			r = djson["result"] == "ok"
			if r!=1:
				print("Server says -> {0} ".format(data))
			return r
		except:
			e = sys.exc_info()[0]
			print("http-post: error. "+str(e))
			return 0 


	def file_get_contents(self,filename):
		with open(filename) as f:
			return f.read()

	def file_put_contents(self,filename,data):
		with open(filename,'w') as f:
			f.write(data)
			f.close()

	def postValues(self,values):
		filePath = os.path.join(tempfile.gettempdir(), self.id+".pickle")
		if self.faildate==0:
			self.faildate = time.strftime("%Y-%m-%d-%H-%M-%S")
		filePath2 = os.path.join(os.path.dirname(__file__), "pending."+self.id+"."+self.faildate+".pickle")

		if os.path.isfile(filePath) and os.path.getsize(filePath)>0:
			ovalues = pickle.loads(self.file_get_contents(filePath))
			print(ovalues)

			print("previous queue size has "+str(len(ovalues))+" entries")
			values = ovalues + values
			os.remove(filePath)
			print(values)

		if not self.httpPost(values):
			n = len(values)
			print("upload not ok... there are now {0} entries pending ({1}).".format(n,filePath))
			self.file_put_contents(filePath,pickle.dumps(values))

			if n>15:
				self.writecnt+=1
				if self.writecnt>10:
					#only write every 10 times to prevent from wearing the flash
					self.file_put_contents(filePath2,pickle.dumps(values))
					print("Writing to persistent storage: "+filePath2)
					self.writecnt = 0

			if n>1000:
				print("Persitent storage file is too big ({}) -- reseting to new file ".format(n))
				self.faildate = 0
				os.remove(filePath)
		else:
			print("Data posting ok!")
			self.faildate = 0
			if os.path.isfile(filePath2):
				print("Deleting persistent storage file "+filePath2)
				os.remove(filePath2)

class ShinyeiDataUploader(SensorDataUploader):

	def post(self,values):
		idat1= dict( value=values[0], type='shinyei-pdp42ns-1u', unit='lpo', time=datetime.now().isoformat() )
		idat2= dict( value=values[1], type='shinyei-pdp42ns-2.5u', unit='lpo', time=datetime.now().isoformat() )
		self.postValues([idat1,idat2])


def loop():
	reader = ShinyeiLpoReader("gpio7","gpio6")
	uploader = ShinyeiDataUploader("shinyei.test-sensor")
	while 1:
		ratio = reader.read(60)
		print ("--- {0} --- {1} {2} ---".format(time.strftime("%H:%M:%S"),ratio[0],ratio[1]))
		uploader.post(ratio)

if __name__ == "__main__":
	loop()

