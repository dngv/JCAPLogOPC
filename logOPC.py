from time import sleep
from smtpvars import * # gitignore email credentials
from opcvars import * # gitignore opc server stuff
import OpenOPC
import smtplib


def readtagd(csv): # csv format: tag, type, description, normal value (optional)
	f = open(csv, mode = 'r')
	rawlist = f.readlines()
	f.close
	d = {}
	tags = []
	for line in rawlist: # csv has no headers
		v = line.split(',')
		tag = 'PVI.PLC.' + v[0]
		dtype = v[1]
		desc = v[2].strip('\n')
		vlist = [dtype, desc]
		if len(v) > 3: # for alarm booleans
			vlist.append(bool(int(v[3].strip('\n'))))
		d[tag] = vlist
	return(d)

alarmd = readtagd('alarmtags.csv')
statsd = readtagd('statustags.csv')
faulttag = 'PVI.PLC.Fault'
runtag = 'PVI.PLC.Run'

opc = OpenOPC.client() # DCOM is faster and .close() doesn't reset this binding

def mainloop(cyctime = 1, faultcy = 5, statcy = 10):
	print 'Alarm loop started.'
	c = 1 # init cycle counter
	run = False # init run in progress
	ran = False # init run ended
	fault = False # init global fault
	mesg = False # init alert sent
#	clist = [faultcy, statcy]
#	flist = ['fault, run, mesg = faultchk(fault, run, mesg)', 'statchk()']
	while True:
		if run:
			if not ran:
				ran = True
				print 'Run started.'
#			blist = map(lambda(x): c % x == 0, clist)
#			for i in range(len(blist)):
#				if blist[i]:
#					exec(flist[i])
			if c % faultcy == 0:
				fault, run, mesg = faultchk(fault, run, mesg)
			if c % statcy == 0:
				statchk()
			if c == lcmm(faultcy, statcy): # lowest common multiple for % x == 0 cases
				c = 0
			c += 1
		else:
			run, ran = runchk(run, ran)
		sleep(cyctime)
	
def runchk(run, ran): # loop when system is idle
	opc.connect(opc_server)
	run, state, time = opc.read(runtag)
	opc.close()
	if ran & (not run):
		mailalert(subject = 'Run fininshed.', body = 'Run has ended. \n')
		ran = False
		print 'Run has ended.'
	print run, ran
	return(run, ran)

def faultchk(fault, run, mesg): # loop when system is running
    opc.connect(opc_server)
    fault, state, time = opc.read(faulttag)
    run, state, time = opc.read(runtag)
    opc.close()
    if fault & (not mesg):
        mailalert()
        mesg = true
        print 'Alert message sent to: ' + to
    if mesg & (not fault):
        mailalert(subject = 'Interlock cleared.', body = 'Last interlock cleared. \n')
        mesg = false
        print 'Interlock clear message sent to: ' + to
    return(fault, run, mesg)
    
def statchk(): # print furnace stats
    opc.connect(opc_server)
    stats = opc.read(statsd.keys())
    opc.close()
    for i in stats:
        key, val, stat, t = i
        print statsd[key][1] + ': ' + str(val)

def readalarms():
	opc.connect(opc_server)
	alarms = opc.read(alarmd.keys())
	opc.close()
	alarmlist = []
	for i in alarms:
		key, val, stat, t = i
		if not alarmd[key][2] == val:
			alarmlist.append(alarmd[key][1])
	alarmtext = '\nThe following alarms are active: \n' + '\n'.join(alarmlist)
	return(alarmtext)
	
def mailalert(to = to, subject = subject, body = readalarms()):
	smtpserv = smtplib.SMTP(smtphost, 587)
	smtpserv.ehlo()
	smtpserv.starttls()
	smtpserv.ehlo
	smtpserv.login(mailuser, mailpass)
	header = 'To:' + to + '\n' + 'From: ' + mailuser + '\n' + subject + '\n'
	msg = header + body
	smtpserv.sendmail(mailuser, to, msg)
	smtpserv.close()

def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b:      
        a, b = b, a % b
    return a

def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)

def lcmm(*args):
    """Return lcm of args."""   
    return reduce(lcm, args)
	
# check fault loop, short delay but only read 1 tag -- DEPRECATED
#def faultloop(delay = 5): # delay in seconds
#	v = False
#	while not v:
#		opc.connect(opc_server)
#		v, s, t = opc.read(faulttag)
#		opc.close()
#		if v:
#			mailalert()
#			print 'Alert message sent to: ' + to
#			break
#		sleep(delay)

#def statloop(delay = 10): # -- DEPRECATED
#	v = True
#	while v:
#		opc.connect(opc_server)
#		v, s, t = opc.read(faulttag)
#		opc.close()
#		if not v:
#			mailalert(body = 'Last interlock cleared. \n')
#			break
#		sleep(delay)
