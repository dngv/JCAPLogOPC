from time import sleep, strftime
from smtpvars import * # gitignore email credentials
from opcvars import * # gitignore opc server stuff
import OpenOPC
import smtplib
import os
import gc

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

alarmtags = readtagd('alarmtags.csv')
stattags = readtagd('statustags.csv')
faulttag = 'PVI.PLC.Fault'
steptag = 'PVI.PLC.Run_step'
sensheader = ','.join(['#time', 'H2S_hood', 'H2S_exhaust', 'NH3_hood', 'NH3_exhaust', 'PH3_exhaust', 'O2_enclosure', 'Chamber_10_torr', 'Chamber_1K_torr', 'Left_temp', 'Left_sp', 'Center_temp', 'Center_sp', 'Right_temp', 'Right_sp', 'Run_no', 'Step'])
#senslist=['Hood_H2S_level', 'Exhaust_H2S_level', 'Hood_NH3_level', 'Exhaust_NH3_level', 'Hood_PH3_level', 'O2_level']
senslist = [('Hood_H2S_level', '%d', 1), \
            ('Exhaust_H2S_level', '%d', 1), \
            ('Hood_NH3_level', '%d', 1), \
            ('Exhaust_NH3_level', '%d', 1), \
            ('Hood_PH3_level', '%d', 1), \
            ('O2_level', '%.1f', 0.1), \
            ('Chamber_10_torr', '%.4f', (10.0/65535)), \
            ('Chamber_1K_torr', '%.1f', (1000.0/65535)), \
            ('Left_heater_PV', '%.1f', 0.1), \
            ('Left_heater_SP', '%.1f', 0.1), \
            ('Center_htr_PV', '%.1f', 0.1), \
            ('Center_htr_SP', '%.1f', 0.1), \
            ('Right_htr_PV', '%.1f', 0.1), \
            ('Right_htr_SP', '%.1f', 0.1), \
            ('Run_number', '%d', 1), \
            ('Run_step', '%d', 1)]

opc = OpenOPC.client() # DCOM is faster and .close() doesn't reset this binding

def mainloop(cyctime = 5, faultcy = 5, statcy = 5):
    print 'Alarm loop started.'
    c = 1 # init cycle counter
    run = False # init run in progress
    ran = False # init run ended
    fault = False # init global fault
    mesg = False # init alert sent
    while True:
#        if run:
#            if not ran:
#                ran = True
#                print 'Run started.'
#            if c % faultcy == 0:
#                fault, run, mesg = faultchk(fault, run, mesg)
#            if c % statcy == 0:
#                statchk()
#            if c == lcmm(faultcy, statcy): # lowest common multiple for % x == 0 cases
#                c = 0
#            c += 1
#        else:
#            run, ran = runchk(run, ran)
#            statchk()
        statchk()
        gc.collect()
        sleep(cyctime)
	
def runchk(run, ran): # loop when system is idle
    opc.connect(opc_server)
    step, state, time = opc.read(steptag)
    opc.close()
    if step > 0:
        run = True
    if ran & (not run):
        mailalert(subject = 'Run fininshed.', body = 'Run has ended. \n')
        ran = False
        print 'Run has ended.'
    print run, ran
    return(run, ran)

def faultchk(fault, run, mesg): # loop when system is running
    opc.connect(opc_server)
    fault, state, time = opc.read(faulttag)
    step, state, time = opc.read(steptag)
    opc.close()
    if step == 0:
        run = False
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
    statsd = {key.split('.')[-1]: val for key, val, stat, t in opc.read(stattags.keys())}
    opc.close()
    for key in statsd.keys():
        print key + ': ' + str(statsd[key])
    writesens(statsd)

def writesens(statsd):
    dailylog = strftime('%Y%m%d') + '.csv'
    logpath = os.path.join(savedir, dailylog)
    if (not os.path.exists(logpath)):
        logfile = open(logpath, mode = 'w')
        logfile.write(sensheader + '\n')
        logfile.close()
    logfile = open(logpath, mode = 'a')
    sensdata = [strftime('%X')]
    for key, fmt, scale in senslist:
        sensdata+=[fmt %(float(statsd[key])*scale)]
        #print key + ': ' + str(statsd[key])
    logfile.write(','.join(sensdata)+'\n')
    logfile.close()

def readalarms():
    opc.connect(opc_server)
    alarms = opc.read(alarmtags.keys())
    opc.close()
    alarmlist = []
    for i in alarms:
        key, val, stat, t = i
        if not alarmtags[key][2] == val:
            alarmlist.append(alarmtags[key][1])
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
	