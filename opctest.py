from time import sleep
from smtpvars import * # gitignore email credentials
from opcvars import * # gitignore opc server stuff
import OpenOPC

opc = OpenOPC.client() # DCOM is faster and .close() doesn't reset this binding
# opc = OpenOPC.open_client(gateway_host)

# check fault loop, short delay but only read 1 tag
def faultloop(delay=1): # delay in seconds
	v=False
	while not v:
		opc.connect(opc_server)
		v, s, t=opc.read(faulttag)
		opc.close()
		print v
		sleep(delay)
	mailalert()
	
def mailalert(to=to, subject=subject):
	smtpserv.ehlo()
	smtpserv.starttls()
	smtpserv.ehlo
	smtpserv.login(mailuser, mailpass)
	header = 'To:' + to + '\n' + 'From: ' + mailuser + '\n' + subject + '\n'
	msg = header + '\n this is test msg from furnace \n\n'
	smtpserv.sendmail(mailuser, to, msg)
	print 'Alert message sent to: ' + mailuser
	smtpserv.close()
	

#def readalarms(delay=15): # delay in seconds
#	while i < count:
#		opc.connect(opc_server)
#		stuff=opc.read(taglist)
#		opc.close()
#		d={}
#		for tag in stuff:
#			d[tag[0]]=tag[1]
#		print d
#		sleep(delay)
#		i+=1

