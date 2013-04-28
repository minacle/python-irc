#!/usr/bin/python
# -*- coding: utf-8 -*-

from irc import irc
import time

network = irc.network("Ozinger")
network.servers.append(irc.server("irc.ozinger.org", 6667))
user = irc.user(nick="pyirctest")
client = irc(network, user, threaded=True)

def recv(irc, text):
	print "RECV << %s" % text
client.received += recv

def sent(irc, text):
	print "SENT >> %s" % text
client.sent += sent

def _001(irc, msg):
	irc.send("join", "#pyirctest")
client.rpl["001"] += _001

def _join(irc, msg):
	if msg.sender.nick == irc.user.nick:
		irc.send("privmsg", msg.args[0], "Hello, World!")
		time.sleep(5)
		irc.send("quit")
client.msg["JOIN"] += _join

if __name__ == "__main__":
	client.start()
	client.join()

