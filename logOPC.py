import OpenOPC
import smtplib
import os
import gc

from time import sleep, strftime
from smtpvars import to, mailuser, mailpass, subject, smtphost # gitignore email credentials
from opcvars import gateway_host, opc_host, opc_server, savedir # gitignore opc server stuff

def readtagd(csv): # csv format: tag, type, description, normal value (optional)
	f = open(csv, mode = 'r')
	rawlist = f.readlines()
	f.close
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
stattags = readtagd('statustags.csv')
faulttag = 'PVI.PLC.Fault'
steptag = 'PVI.PLC.Run_step'

sensheader = ','.join(['#time', \
                        'H2S_hood', \
                        'H2S_exhaust', \
                        'NH3_hood', \
                        'NH3_exhaust', \
                        'PH3_exhaust', \
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
                        'Step'])
                        
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

def mainloop(cyctime = 5):

    lastrun = False # previous cycle run value
    lastalarm = False # previous cycle alarm value
    
    def printmsg(msg):
        currenttime = strftime('%Y%m%d %H:%M:%S')
        print(currenttime + ' - ' + msg)

    opc = OpenOPC.open_client(gateway_host)
    printmsg('Alarm loop started.')
    opc.connect(opc_server, opc_host)
    
    def statchk(): # print furnace stats
        statsd = {key.split('.')[-1]: val for key, val, stat, t in opc.read(stattags.keys())}
#        for key in statsd.keys():
#            print key + ': ' + str(statsd[key])
#        print '\n'
        writesens(statsd)
        return(statsd)

    def writesens(statsd):
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
        for key, fmt, scale in senslist:
            sensdata+=[fmt %(float(statsd[key])*scale)]
#        print '\n'
        if (len(sensdata)==(len(senslist)+1)): # only write log if we have all data fields
            try:
                logfile = open(logpath, mode = 'a')
                logfile.write(','.join(sensdata)+'\n')
                logfile.close()
            except:
                printmsg('Unable to write to log file.')
                pass

    def readalarms():
        alarms = opc.read(alarmtags.keys())
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
            return(run)

        if(run==False and lastrun==True):
            # send message run ended
            try:
                mailalert(subject='Run #' + str(d['Run_number']) + ' has finished.', body='')
                printmsg('Stop message sent.')
            except:
                printmsg('Unable to send end message.')
                pass
            return(run)
        
    def alarmchk(d):
        alarm=bool(d['Fault'])
        if(alarm==True and lastalarm==False):
            # send message alarm triggered
            try:
                mailalert()
                printmsg('Alarm message sent.')
            except:
                printmsg('Unable to send alarm message.')
                pass
            return(alarm)
            
        if(alarm==False and lastalarm==True):
            # send message alarm cleared
            try:
                mailalert(subject='Furnace interlock cleared.')
                printmsg('Alarm cleared message sent.')
            except:
                printmsg('Unable to send clear message.')
                pass
            return(alarm)

    try:
        while True:
            try:
                d=statchk()
                lastrun=runchk(d)
                lastalarm=alarmchk(d)
            except:
                #printmsg('Last run = ' str(lastrun))
                #printmsg('Last alarm = ' str(lastalarm))
                pass
            gc.collect()
            sleep(cyctime)
    except KeyboardInterrupt:
        printmsg('Ctrl-C pressed. Exiting loop.')

    opc.close()

	