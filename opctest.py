from time import sleep
from smtpvars import * # gitignore email credentials
from opcvars import * # gitignore opc server stuff
import OpenOPC
import smtplib

def readtagd(csv): # csv format: tag, type, description, normal value (optional)
	f=open(csv, mode='r')
	rawlist=f.readlines()
	f.close
	d={}
	tags=[]
	for line in rawlist: # csv has no headers
		v=line.split(',')
		tag='PVI.PLC.'+v[0]
		dtype=v[1]
		desc=v[2].strip('\n')
		vlist=[dtype, desc]
		if len(v)>3: # for alarm booleans
			vlist.append(bool(int(v[3].strip('\n'))))
		d[tag]=vlist
	return(d)

alarmd=readtagd('alarmtags.csv')
statsd=readtagd('statustags.csv')
faulttag='PVI.PLC.Fault'

opc = OpenOPC.client() # DCOM is faster and .close() doesn't reset this binding

def mainloop(dontstop=True):
	while dontstop:
		faultloop()
		statloop()
		sleep(5)
	
# check fault loop, short delay but only read 1 tag
def faultloop(delay=5): # delay in seconds
	v=False
	while not v:
		opc.connect(opc_server)
		v, s, t=opc.read(faulttag)
		opc.close()
		if v:
			mailalert()
			print 'Alert message sent to: ' + to
			break
		sleep(delay)

def statloop(delay=10):
	v=True
	while v:
		opc.connect(opc_server)
		v, s, t=opc.read(faulttag)
		opc.close()
		if not v:
			mailalert(body='Last interlock cleared. \n')
			break
		sleep(delay)

def readalarms():
	opc.connect(opc_server)
	alarms=opc.read(alarmd.keys())
	opc.close()
	alarmlist=[]
	for i in alarms:
		key, val, stat, t = i
		if not alarmd[key][2]==val:
			alarmlist.append(alarmd[key][1])
	alarmtext='\nThe following alarms are active: \n' + '\n'.join(alarmlist)
	return(alarmtext)
	
def mailalert(to=to, subject=subject, body=readalarms()):
	smtpserv = smtplib.SMTP(smtphost, 587)
	smtpserv.ehlo()
	smtpserv.starttls()
	smtpserv.ehlo
	smtpserv.login(mailuser, mailpass)
	header = 'To:' + to + '\n' + 'From: ' + mailuser + '\n' + subject + '\n'
	msg = header + body
	smtpserv.sendmail(mailuser, to, msg)
	smtpserv.close()


	

