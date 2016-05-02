import OpenOPC
import smtplib
import os
import gc
import subprocess

from time import sleep, strftime, localtime
from smtpvars import to, mailuser, mailpass, subject, smtphost # gitignore email credentials
from opcvars import gateway_host, opc_host, opc_server, savedir # gitignore opc server stuff
from prettytable import PrettyTable

def cls():
    os.system('cls' if os.name=='nt' else 'clear')

def readtagd(csv): # csv format: tag, type, description, normal value (optional)
	f = open(csv, mode = 'r')
	rawlist = f.readlines()
	f.close()
	d = {}
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
alarmkeys = alarmtags.keys()
alarmkeys.sort()
stattags = readtagd('statustags.csv')
faulttag = 'PVI.PLC.Fault'
steptag = 'PVI.PLC.Run_step'

bcycles = ['1', '5', '15', '30', '60', '120', '300', '600']
ablength = 8
ab = []

sensheader = ','.join(['#time', \
                        'H2S_hood', \
                        'H2S_exhaust', \
                        'NH3_hood', \
                        'NH3_exhaust', \
                        'PH3_hood', \
                        'O2_enclosure', \
                        'Chamber_10_torr', \
                        'Chamber_1K_torr', \
                        'Left_temp', \
                        'Left_sp', \
                        'Center_temp', \
                        'Center_sp', \
                        'Right_temp', \
                        'Right_sp', \
                        'Run_no', \
                        'Step', \
						'Manifold_torr', \
						'Pump_inlet'])

senslist = [('Hood_H2S_level', '%.1f', 1, 0), \
            ('Exhaust_H2S_level', '%.1f', 1, 0), \
            ('Hood_NH3_level', '%.1f', 1, 0), \
            ('Exhaust_NH3_level', '%.1f', 1, 0), \
            ('Hood_PH3_level', '%.2f', (1/7), -3), \
            ('O2_level', '%.1f', 0.1, 0), \
            ('Chamber_10_torr', '%.4f', (10.0/65535), 0), \
            ('Chamber_1K_torr', '%.1f', (1000.0/65535), 0), \
            ('Left_heater_PV', '%.1f', 0.1, 0), \
            #('Left_heater_SP', '%.1f', 0.1, 0), \
            ('Center_htr_PV', '%.1f', 0.1, 0), \
            #('Center_htr_SP', '%.1f', 0.1, 0), \
            ('Right_htr_PV', '%.1f', 0.1, 0), \
            #('Right_htr_SP', '%.1f', 0.1, 0), \
            #('Run_number', '%d', 1, 0), \
            ('Run_step', '%d', 1, 0), \
			('Manifold_10_torr', '%.3f', (10.0/65535), 0), \
			('Pump_press', '%.4f', 1, 0)]

def mainloop(rectime = 5):

    lastrun = False # previous cycle run value
    lastalarm = False # previous cycle alarm value
    safealarmvals = [alarmtags[key][2] for key in alarmkeys]
    lastalarmvals = safealarmvals
    cycles = 1
    ncols = len(senslist) + 1 # add 1 for timestamp
    b = {}
    for bc in bcycles:
        b[bc] = ['NaN'] * ncols

    def printmsg(msg):
        global ab
        currenttime = strftime('%Y%m%d %H:%M:%S', localtime())
        #print(currenttime + ' - ' + msg)
        if len(ab) == ablength:
            ab = ab[:-1]
        ab = [currenttime + ' - ' + msg] + ab

    def getsrv():
        srv=[i.strip() for i in subprocess.check_output(['net','start']).split('\r\n')]
        return(srv)

    opcsrvname = 'OpenOPC Gateway Service'

    # check running services
    def checksrv():
        wsrv = getsrv()
        while opcsrvname not in wsrv:
            printmsg('OpenOPC gateway service not running. Attempting to start.')
            subprocess.call(['net','stop','zzzOpenOPCService'])
            subprocess.call(['net','start','zzzOpenOPCService'])
            wsrv = getsrv()

    checksrv()
    opc = OpenOPC.open_client(gateway_host)
    printmsg('Creating OPC client instance...')
    opc.connect(opc_server, opc_host)
    printmsg('OPC server connected.')

    def statchk(): # print furnace stats
	    rawd = {key.split('.')[-1]: val for key, val, stat, t in opc.read(stattags.keys())}
	    eud = {}
	    for key, fmt, scale, offset in senslist:
	        eud[key]=[fmt %((offset+float(rawd[key]))*scale)]
	    return(rawd, eud)

    def writesens(eud):
        dailylog = strftime('%Y%m%d') + '.csv'
        logpath = os.path.join(savedir, dailylog)
        if (not os.path.exists(logpath)):
            try:
                logfile = open(logpath, mode = 'w')
                logfile.write(sensheader + '\n')
                logfile.close()
            except:
                printmsg('Unable to write to log file.')
                return()
        sensdata = [strftime('%X')]
        for key, fmt, scale, offset in senslist:
            sensdata+=eud[key]
        if (len(sensdata)==(len(senslist)+1)): # only write log if we have all data fields
            try:
                logfile = open(logpath, mode = 'a')
                logfile.write(','.join(sensdata)+'\n')
                logfile.close()
            except:
                printmsg('Unable to write to log file.')
                pass

    def mailalert(body, to = to, subject = subject):
        smtpserv = smtplib.SMTP(smtphost, 587)
        smtpserv.ehlo()
        smtpserv.starttls()
        smtpserv.ehlo
        smtpserv.login(mailuser, mailpass)
        header = 'To:' + to + '\n' + 'From: ' + mailuser + '\n' + 'Subject: ' + subject + '\n'
        msg = header + body
        smtpserv.sendmail(mailuser, to, msg)
        smtpserv.close()

    def runchk(d):
        run=d['Run_step']>0
        if(run==True and lastrun==False):
            # send message run started
            try:
                mailalert(subject='Run #' + str(d['Run_number']) + ' has started.', body='')
                printmsg('Start message sent.')
            except:
                printmsg('Unable to send start message.')
                pass
        if(run==False and lastrun==True):
            # send message run ended
            try:
                mailalert(subject='Run #' + str(d['Run_number']-1) + ' has finished.', body='')
                printmsg('Stop message sent.')
            except:
                printmsg('Unable to send end message.')
                pass
        return(run)

    def alarmchk(d):
        alarm=bool(d['Fault'])
        alarms = opc.read(alarmkeys)
        alarmd = {}
        alarmvals = []
        alarmtxtlist = []
        for i in alarms:
            key, val, stat, t = i
            alarmd[key] = val
            if not alarmtags[key][2] == val:
                alarmtxtlist.append(alarmtags[key][1])
        for key in alarmkeys:
            alarmvals += [alarmd[key]]
        alarmtext = '\nThe following alarms are active: \n' + '\n'.join(alarmtxtlist)
        if((alarm==True and lastalarm==False) or ((alarmvals != lastalarmvals) and (alarmvals != safealarmvals))):
            # send message alarm triggered
            try:
                mailalert(body = alarmtext)
                printmsg('Alarm message sent.')
            except:
                printmsg('Unable to send alarm message.')
                pass
        if((alarm==False and lastalarm==True) and (alarmvals == safealarmvals)):
            # send message alarm cleared
            try:
                mailalert(subject='Furnace interlock cleared.', body='All alarms cleared.')
                printmsg('Alarm cleared message sent.')
            except:
                printmsg('Unable to send clear message.')
                pass
        return(alarm, alarmvals)

    def printstats(eud):
        t = PrettyTable(['Time'] + [key for key, fmt, scale, offset in senslist])
        for bc in bcycles[::-1]:
            if int(bc) == 1:
                b[bc] = [strftime('%X')] + [eud[k][0] for k in [key for key, fmt, scale, offset in senslist]]
            elif cycles % int(bc) == 0:
                b[bc] = b[bcycles[bcycles.index(bc)-1]] # propagate value down list
    	    t.add_row(b[bc])
        cls()
        t.border = False
    	print t
        print 'Last 8 messages:'
        for alm in ab[::-1]:
            print alm

    printmsg('Alarm loop started.')
    try:
        while True:
            try:
                rd, ed = statchk()
                lastrun=runchk(rd)
                lastalarm, lastalarmvals=alarmchk(rd)
                if cycles % rectime == 0:
                    writesens(ed)
                if cycles == max([int(c) for c in bcycles]):
                    cycles = 1
                printstats(ed)
                cycles = cycles + 1
            except:
                cycles = 1
                checksrv()
                opc = OpenOPC.open_client(gateway_host)
                opc.connect(opc_server, opc_host)
                pass
            gc.collect()
            sleep(1)
    except KeyboardInterrupt:
        printmsg('Ctrl-C pressed. Exiting loop.')
        try:
            rd, ed = statchk()
            printstats(ed)
        except:
            pass

    opc.close()
