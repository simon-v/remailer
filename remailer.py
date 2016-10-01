#!/usr/bin/python2 -B
# Import the public GPG key for the persons allowed to post into the keyring on the server
# Add the From: strings for the persons allowed to post to the allowed sender list
# Create an exim filter that pipes emails coming to your list into this script

# -----===== CONFIGURATION =====-----
files = {
	'headers': '%s/headers.txt',  # Email headers to be included in sent messages
	'subscribers': '%s/subscribers.txt',  # List of newsletter subscribers
	'welcome': '%s/welcome.txt',  # The message sent when someone subscribes
	'farewell': '%s/farewell.txt',  # The message sent when someone unsubscribes
	'confirmation': '%s/confirm.txt',  # The message sent when someone requests subscription
	'details_missing': '%s/details_missing.txt',  # The message sent when a details request is made on a non-existent email
	'details_verified': '%s/details_verified.txt',  # The message sent when a details request is made on a verified email
	'details_pending': '%s/details_pending.txt',  # The message sent when a details request is made on an email pending verification
	'details_bounced': '%s/details_bounced.txt'  # The message sent when a details request is made on a disabled email
}
# See also remailer.cfg

import sys
import os
import email
import time
import subprocess
import string
import random
import copy
import logging

# Some web hosts are not very diligent in keeping up-to-date
try:
	from email.mime.text import MIMEText  # Python 2.7+
except ImportError:
	from email.MIMEText import MIMEText  # Python 2.4

try:
	from email.mime.multipart import MIMEMultipart  # Python 2.7+
except ImportError:
	from email.MIMEMultipart import MIMEMultipart  # Python 2.4

try:
	from email.utils import parseaddr  # Python 2.7+
except ImportError:
	from email.Utils import parseaddr  # Python 2.4

# Those are local scripts put in the same directory
import clearmime

# Abort the execution leaving sending the list owner a backtrace
def panic(error):
	logging.error('Panicking: %s' % error)
	debug_file = '%s.eml' % time.time()
	df = open(debug_file, 'w')
	df.write(raw_email)
	df.close()
	logging.error('Offending message saved to "%s"' % debug_file)
	sys.exit()

# Configuration file parsing and validation
# The simplicity of this implementation does not warrant employing a ConfigParser
conf = {}
try:
	c = open('remailer.cfg', 'r')
	for l in c.readlines():
		k, v = l.strip().split('=')[0], l.strip().split('=')[1:]
		if type(v) == type([]):
			v = '='.join(v)
		conf[k] = v
	c.close()
except:
	panic('No configuration file found')
for s in ['backend', 'server', 'login', 'passwd', 'allowed_senders', 'list_owner', 'gnupg_file']:
	if s not in conf:
		panic('`%s` key is missing from configuration file' % s)

# Send one or more pre-constructed emails
def sendmail(message_list):
	if type(message_list) != type([]):
		message_list = [message_list]
	sent_count = 0
	if conf['backend'] == 'smtp':
		import smtplib
		try:
			logging.info('Connecting to SMTP server')
			server = smtplib.SMTP(conf['server'])
			server.login(conf['login'], conf['passwd'])
		except:
			panic('SMTP failed: %s' % sys.exc_info()[0])
		for message in message_list:
			try:
				server.sendmail(message['From'], message['To'], message.as_string())
			except:
				logging.error('Sending to %s failed: %s' % (message['To'], sys.exc_info()[0]))
			else:
				sent_count += 1
				#logging.debug('Sent to %s' % message['To'])
		server.quit()
	elif conf['backend'] == 'sendmail':
		for message in message_list:
			try:
				server = subprocess.Popen(['/usr/sbin/sendmail','-i', '-t'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
				_, stderr = server.communicate(message.as_string())
				if stderr != '':
					logging.error('Sending to %s failed' % message['To'])
					logging.error(stderr)
			except:
				logging.error('Sendmail failed: %s' % sys.exc_info()[0])
			else:
				sent_count += 1
	elif conf['backend'] == 'dummy':
		logging.info('Pretending to send messages')
	else:
		panic('Back-end for sending mail is not configured')
	if sent_count == 0:
		panic('No valid recipients for %s' % list_name)
	else:
		logging.info('%s message(s) sent' % sent_count)


# Extract a relevant record from the subscriber database
def find_subscriber(subscriber):
	try:
		rfile = open(files['subscribers'])
	except:
		panic('Could not load subscriber list for %s: %s' % (list_name, sys.exc_info()[0]))
	else:
		for raw_recipient in rfile:
			if raw_recipient == '\n':
				continue
			recipient = raw_recipient.strip().split('	')
			r_name, r_email = parseaddr(recipient[0])
			if r_email == subscriber:
				rfile.close()
				return recipient
		return None

# Extract the message sender
def get_sender(message):
	address = None
	for header in ['From', 'From_', 'Reply-To']:
		if not message[header] == None:
			_, address = parseaddr(message[header])
			return address
	panic('Could not find the sender address')

# Load a file as message
def message_from_file(filename, args=()):
	try:
		wfile = open(filename)
	except:
		panic('Could not load %s: %s' % (filename, sys.exc_info()[0]))
	else:
		message = MIMEText(wfile.read() % args)
		wfile.close()
	message['From'] = '%s-request@simonvolpert.com' % list_name
	message['Auto-Submitted'] = 'auto-responded'
	return message

# Send a report about a subscriber
def report(address):
	subscriber = find_subscriber(address)
	if subscriber == None:
		message = message_from_file(files['details_missing'] , address)
		message['Subject'] = 'Email not found'
	else:
		if subscriber[3] == 'verified':
			message = message_from_file(files['details_verified'], (subscriber[0], subscriber[1], subscriber[2], subscriber[4]))
			message['Subject'] = 'Subscription details'
		elif subscriber[3] == 'bounce':
			message = message_from_file(files['details_bounced'], (subscriber[0], subscriber[1], subscriber[2]))
			message['Subject'] = 'Subscription disabled'
		else:
			message = message_from_file(files['details_pending'], (subscriber[0], subscriber[1], subscriber[2]))  # TODO make it double as a re-subscription, maybe
			message['Subject'] = 'Verification pending'
	message['To'] = address
	sendmail(insert_headers(message))
	sys.exit()

# Insert mailing-list headers into the message
def insert_headers(message):
	try:
		hfile = open(files['headers'])
	except:
		panic('Could not load header list for %s: %s' % (list_name, sys.exc_info()[0]))
	else:
		for line in hfile:
			header, header_text = line.strip().split('|')
			message[header] = header_text
		hfile.close()
	return message


# -----===== EMAIL PROCESSING =====-----
os.chdir(sys.path[0])

logging.basicConfig(filename='remailer.log', level=logging.DEBUG, format='%(asctime)s  %(message)s')

# This script works on emails piped into it
raw_email = sys.stdin.read()
message = email.message_from_string(raw_email)

logging.info('Incoming message from %s (%s bytes)' % (message['From'], len(raw_email)))

# Figure out the list name from the message headers
# Recipients checked in reverse order of directness
list_name = None
for header in ['To', 'CC', 'BCC']:
	if not message[header] == None:
		_, list_name = parseaddr(message[header])
if list_name == None:
	panic('Could not figure out the list name')
else:
	list_name = list_name.split('@')[0]
	if list_name.endswith('-request'):
		list_name = list_name.split('-')[0]
		request = True
		logging.info('REQUEST mode on "%s"' % list_name)
	else:
		request = False
		logging.info('POST mode on "%s"' % list_name)
	for item in files:
		files[item] = files[item] % list_name
	# Delete original message recipients
	for header in ['To', 'CC', 'BCC']:
		if not message[header] == None:
			del message[header]

# -----===== SUBSCRIPTION MANAGEMENT =====-----
if request:
	# If it's an auto-response, discard it
	if message['Auto-Submitted'] != None:
		panic('Message is an auto-response')
	# -----===== SUBSCRIBE =====-----
	logging.info('Subject: %s' % message['Subject'])
	if message['Subject'].lower().startswith('subscribe'):
		message_from = get_sender(message)
		subscriber = find_subscriber(message_from)
		if not subscriber == None:
			if subscriber[3] == 'verified':
				report(subscriber[0])
			else:
				# Comment out for dry-run
				subprocess.call(['sed', '-i', '-e', '/%s/d' % subscriber[0], files['subscribers']])
				logging.info('Subscriber info UPDATED for %s' % subscriber[0])
		now = time.asctime(time.gmtime())
		medium = 'email'
		subscriber = [message_from, now, medium, '']
		subscriber[3] = ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(8))
		# Comment out for dry-run
		sfile = open(files['subscribers'], 'a')
		sfile.write('	'.join(subscriber) + '\n')
		sfile.close()
		logging.info('Subscriber info WRITTEN for %s' % subscriber[0])
		message = message_from_file(files['confirmation'], (message_from, now, medium))
		message['To'] = subscriber[0]
		message['Subject'] = 'Confirm your subscription - %s' % subscriber[3]
		sendmail(insert_headers(message))
	# -----===== UNSUBSCRIBE =====-----
	elif message['Subject'].lower().startswith('unsubscribe'):
		message_from = get_sender(message)
		subscriber = find_subscriber(message_from)
		if subscriber == None:
			report(message_from)
		else:
			# Comment out for dry-run
			subprocess.call(['sed', '-i', '-e', '/%s/d' % subscriber[0], files['subscribers']])
			logging.info('Subscriber info REMOVED for %s' % subscriber[0])
			message = message_from_file(files['farewell'], message_from)
			message['To'] = subscriber[0]
			message['Subject'] = 'Unsubscription successful'
			sendmail(insert_headers(message))
	# -----===== DETAILS =====-----
	elif message['Subject'].lower().startswith('details') or message['Subject'].lower().startswith('status') or message['Subject'].lower().startswith('info'):
		report(get_sender(message))
	# -----===== CONFIRM =====-----
	elif message['Subject'].lower().startswith('re: confirm '):
		message_from = get_sender(message)
		subscriber = find_subscriber(message_from)
		if not subscriber == None:
			if subscriber[3] == 'verified' or subscriber[3] == 'bounce':
				report(subscriber[0])
		confirm_string = message['Subject'].split(' ')[-1]
		message_from = get_sender(message)
		subscriber = find_subscriber(message_from)
		if subscriber == None:
			report(message_from)
		else:
			if confirm_string == subscriber[3]:
				# Comment out for dry-run
				subprocess.call(['sed', '-i', '-e', 's/%s.*/verified	%s/' % (confirm_string, time.asctime(time.gmtime())), files['subscribers']])
				logging.info('Subscriber info UPDATED for %s' % subscriber[0])
				message = message_from_file(files['welcome'])
				message['To'] = subscriber[0]
				message['Subject'] = 'Confirmation successful'
				sendmail(insert_headers(message))
			else:
				panic('Confirmation string does not match')
	else:
		panic('Unknown command')
# -----===== PUBLISHING =====-----
else:
	# Bounce unknown senders # TODO
#	if get_sender(message) not in conf.allowed_senders:
#		panic('Unauthorized sender: %s' % message['From'])
	if message['From'] != conf['list_owner']:
		panic('Unauthorized sender: %s' % message['From'])

	# Verify the message sender's GPG signature
	clear_email = clearmime.clarify(raw_email)
	server = subprocess.Popen(['gpgv', '--keyring', conf['gnupg_file']], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
	_, stderr = server.communicate(clear_email)
	if not ( 'gpgv: Good signature from "%s"' % conf['list_owner'] in stderr ): # TODO expand to all allowed-senders
		logging.info(stderr)
		panic('GPG Signature verification failed')
	logging.info('Signature check successful')

	message = insert_headers(message)
	# Re-send the email to every verified subscriber from the subscriber list
	# Format: email, subscription date, subscription medium, status, confirmation date (tab separated)
	try:
		rfile = open(files['subscribers'])
	except:
		panic('Could not load subscriber list for %s: %s' % (list_name, sys.exc_info()[0]))
	message_list = []
	for recipient in rfile:
		if recipient == '\n':
			continue
		recipient = recipient.strip().split('	')
		if not recipient[3] == 'verified':
			continue
		del message['To']
		message['To'] = recipient[0]
		message_list.append(copy.copy(message))
	rfile.close()
	sendmail(message_list)
