## Simple test script for Matrikon OPC simulation server
## https://www.matrikonopc.com/downloads/178/index.aspx

import OpenOPC
from time import sleep

opc = OpenOPC.client()
opc.connect('Matrikon.OPC.Simulation.1')

def readloop(tag, count=1, delay=1):
	i=0
	while i < count:
		print opc.read(tag)
		sleep(delay)
		i+=1

readloop('Random.ArrayOfReal8', 1000)

opc.close()