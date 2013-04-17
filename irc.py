# -*- coding: utf-8 -*-

# Copyright © Minacle 2012-2013.

import socket
import json, re, sys
import time, threading

from customevent import event


class irc(threading.Thread):
  
	class network(object):
		
		def __init__(self, name, servers=[], encoding="utf-8", *args, **kwargs):
			self.name = name
			for i, server in enumerate(servers):
				if type(server) is not irc.server:
					servers[i] = irc.server(**server)
			self.servers = servers
			self.encoding = encoding
		
		def __str__(self):
			ext = {}
			ext[u"name"] = self.name
			ext[u"encoding"] = self.encoding
			ext[u"servers"] = self.servers
			return str(ext)
		
		def __repr__(self):
			return str(self)


	class server(object):
		
		def __init__(self, host, port=6667, *args, **kwargs):
			self.host = host
			self.port = port
		
		def __str__(self):
			ext = {}
			ext[u"host"] = self.host
			ext[u"port"] = self.port
			return str(ext)
		
		def __repr__(self):
			return str(self)


	class channel(object):
		
		def __init__(self, name, key="", *args, **kwargs):
			self.name = name
			self.key = key
			self.users = []
		
		def __str__(self):
			ext = {}
			ext[u"name"] = self.name
			ext[u"key"] = self.key
			return str(ext)
		
		def __repr__(self):
			return str(self)


	class user(object):
		
		@property
		def nobody(self):
			return user(None)
		
		def __init__(self, mask=None, *args, **kwargs):
			if mask is None:
				if "nick" in kwargs:
					self.nick = kwargs["nick"]
					if "name" in kwargs:
						self.name = kwargs["name"]
					else:
						self.name = self.nick
					if "real" in kwargs:
						self.real = kwargs["real"]
					else:
						self.real = self.nick
					if "host" in kwargs:
						self.host = kwargs["host"]
					else:
						self.host = u"0.0.0.0"
				return
			else:
				if "!" in mask and "@" in mask:
					self.nick = mask[:(mask.index("!"))]
					self.name = mask[(mask.index("!") + 1):(mask.index("@"))]
					self.host = mask[(mask.index("@") + 1):]
				else:
					self.nick = self.name = self.host = u""
				self.real = u""
			self.mask = mask
		
		def __str__(self):
			ext = {}
			ext[u"nick"] = self.nick
			ext[u"name"] = self.name
			ext[u"host"] = self.host
			ext[u"real"] = self.real
			return str(ext)
		
		def __repr__(self):
			return str(self)
	
	
	class message(object):
		
		def __init__(self, command, _args=[], sender=None, timestamp=time.time(), *args, **kwargs):
			self.command = command
			self.args = _args
			self.sender = sender
			self.timestamp = timestamp
		
		def __str__(self):
			ext = {}
			ext[u"command"] = self.command
			ext[u"args"] = self.args
			ext[u"sender"] = self.sender
			ext[u"timestamp"] = self.timestamp
			return str(ext)
		
		def __repr__(self):
			return str(self)
			
		@classmethod
		def fromraw(cls, raw):
			command = u""
			args = []
			sender = None
			timestamp = time.time()
			#parse
			if raw.startswith(":"):
				s = raw.split(" ", 1)
				sender = irc.user(s[0][1:])
				raw = s[1]
			_c, _as = raw.split(" ", 1)
			_a = iata(*stia(_as))
			command = _c.upper()
			args = _a
			return cls(command, args, sender, timestamp)
	
	
	def __init__(self, network, user, *args, **kwargs):
		#supers
		threading.Thread.__init__(self)
		self.setDaemon(True)
		#defaults
		self.sock = None
		self.network = network
		self.user = user
		self.chans = {}
		self.users = {}
		self._temp = {}
		#define raw events
		self.main = event() # args: irc
		self.connecting = event() # args: irc
		self.connected = event() # args: irc
		self.failed = event() # args: irc
		self.received = event() # args: irc, text
		self.sent = event() # args: irc, text
		#define irc events
		self.rpl = {}
		for i in range(1, 999):
			self.rpl[unicode("{:03}".format(i))] = event()
		self.msg = {
			u"PASS": event(),
			u"NICK": event(),
			u"USER": event(),
			u"OPER": event(),
			u"MODE": event(),
			u"SERVICE": event(),
			u"QUIT": event(),
			u"SQUIT": event(),
			u"JOIN": event(),
			u"PART": event(),
			u"TOPIC": event(),
			u"NAMES": event(),
			u"LIST": event(),
			u"INVITE": event(),
			u"KICK": event(),
			u"PRIVMSG": event(),
			u"NOTICE": event(),
			u"MOTD": event(),
			u"LUSERS": event(),
			u"VERSION": event(),
			u"STATS": event(),
			u"LINKS": event(),
			u"TIME": event(),
			u"CONNECT": event(),
			u"TRACE": event(),
			u"ADMIN": event(),
			u"INFO": event(),
			u"SERVLIST": event(),
			u"SQUERY": event(),
			u"WHO": event(),
			u"WHOIS": event(),
			u"WHOWAS": event(),
			u"KILL": event(),
			u"PING": event(),
			u"PONG": event(),
			u"ERROR": event(),
			u"AWAY": event(),
			u"REHASH": event(),
			u"DIE": event(),
			u"RESTART": event(),
			u"SUMMON": event(),
			u"USERS": event(),
			u"WALLOPS": event(),
			u"USERHOST": event(),
			u"ISON": event(),
		}
		
		#define initial event handlers
		
		def error(self, msg):
			try:
				self.isconnected = False
				self.sock.close()
			except:
				pass
			self.connect()
		self.msg[u"ERROR"] += error
		
		def ping(self, msg):
			self.send(self.msg["PONG"], msg.args[0])
		self.msg[u"PING"] += ping
		
		def quit(self, msg):
			if msg.sender is None:
				try:
					self.isconnected = False
					self.sock.close()
				except:
					pass
			else:
				for user in self.users.values():
					if user.nick == msg.sender.nick:
						del self.users[user.nick]
						break
				for chan in self.chans.values():
					for user in chan.users:
						if user.nick == msg.sender.nick:
							chan.users.remove(user)
							break
		self.msg[u"QUIT"] += quit
		
		def join(self, msg):
			if msg.sender is None:
				return
			if msg.sender.nick == self.user.nick:
				self.send(self.msg["WHO"], msg.args[0])
			if msg.args[0] not in self.chans.keys():
				self.chans[msg.args[0]] = irc.channel(msg.args[0])
			self.chans[msg.args[0]].users.append(msg.sender)
		self.msg[u"JOIN"] += join
		
		def part(self, msg):
			for user in self.chans[msg.args[0]].users:
				if user.nick == msg.sender.nick:
					self.chans[msg.args[0]].users.remove(user)
					break
		self.msg[u"PART"] += part
		
		def kick(self, msg):
			for user in self.chans[msg.args[0]].users:
				if user.nick == msg.args[1]:
					self.chans[msg.args[0]].users.remove(user)
					break
		self.msg[u"KICK"] += kick
		
		def _001(self, msg):
			self.users[msg.args[0]] = irc.user(nick=msg.args[0])
			self.send(self.msg["WHOIS"], msg.args[0])
		self.rpl[u"001"] += _001
		
		def whois(self, msg):
			if "whois" not in self._temp.keys():
				self._temp["whois"] = {}
		self.msg[u"WHOIS"] += whois
		
		def _311(self, msg):
			self._temp["whois"][msg.args[1]] = {}
			self._temp["whois"][msg.args[1]]["nick"] = msg.args[1]
			self._temp["whois"][msg.args[1]]["user"] = msg.args[2]
			self._temp["whois"][msg.args[1]]["host"] = msg.args[3]
			self._temp["whois"][msg.args[1]]["real"] = msg.args[5]
		self.rpl[u"311"] += _311
		
		def _318(self, msg):
			d = self._temp["whois"][msg.args[1]]
			m = u"%(nick)s!%(user)s@%(host)s" % d
			self.users[d["nick"]] = irc.user(m, real=d["real"])
			if d["nick"] == self.user.nick:
				self.user = self.users[d["nick"]]
			del self._temp["whois"][msg.args[1]]
		self.rpl[u"318"] += _318
		
		def who(self, msg):
			self._temp["who"] = []
		self.msg[u"WHO"] += who
		
		def _352(self, msg):
			self._temp["who"].append({u"chan": msg.args[1], u"user": msg.args[2], u"host": msg.args[3], u"nick": msg.args[5], u"real": msg.args[-1].split(" ", 1)[1]})
		self.rpl[u"352"] += _352
		
		def _315(self, msg):
			ds = self._temp["who"]
			for d in ds:
				self.users[d["nick"]] = irc.user(**d)
				if d["nick"] == self.user.nick:
					self.user = self.users[d["nick"]]
				if self.users[d["nick"]] in self.chans[d["chan"]].users:
					self.chans[d["chan"]].users[self.chans[d["chan"]].users.index(self.users[d["nick"]])] = self.users[d["nick"]]
				else:
					self.chans[d["chan"]].users.append(self.users[d["nick"]])
		self.rpl[u"315"] += _315
	
	def run(self, *args, **kwargs):
		self.connect(*args, **kwargs)
	
	def connect(self, active=None, *args, **kwargs):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connecting(self)
		if type(active) is irc.server and active in self.network:
			self.active = active
		else:
			if active is None:
				active = 0
			self.active = self.network.servers[active]
		try:
			self.sock.connect((self.active.host, self.active.port))
			self.isconnected = True
			self.connected(self)
		except:
			self.isconnected = False
			self.failed(self)
			return
		self.__core__()
	
	def disconnect(self, reason=""):
		try:
			self.send(self.msg["QUIT"], reason)
		except:
			pass
		finally:
			self.isconnected = False
			self.sock.close()
	
	def send(self, cmd, *args, **kwargs):
		if type(cmd) is str:
			cmd = unicode(cmd, "utf-8", errors="ignore")
		if type(cmd) is unicode:
			cmd = self.msg[cmd.upper()]
		args = list(args)
		for i, arg in enumerate(args):
			if type(arg) is str:
				args[i] = unicode(arg, "utf-8", "ignore")
		_cmd = self.msg.keys()[self.msg.values().index(cmd)]
		ext = u" ".join([_cmd, atias(*args)])
		self.sock.send(ext.encode(self.network.encoding) + "\n")
		self.sent(self, ext)
		cmd(self, irc.message(_cmd, atias(*args)))
	
	def __core__(self):
		#init
		data = ""
		#ident
		self.send(self.msg["USER"], self.user.name, "0", "*", self.user.real)
		self.send(self.msg["NICK"], self.user.nick)
		#main
		mainthread = None
		def mainloop():
			while self.isconnected:
				self.main()
				time.sleep(0.05)
		if self.isconnected:
			mainthread = threading.Thread(target=mainloop)
			mainthread.start()
		while self.isconnected:
			buf = self.sock.recv(4096)
			data += buf
			if not data.endswith("\r\n"):
				continue
			lines = data.split("\r\n")
			data = ""
			for line in lines:
				if line == "":
					continue
				line = unicode(line, self.network.encoding, errors="ignore")
				self.received(self, line)
				msg = irc.message.fromraw(line)
				if msg.command in self.rpl:
					self.rpl[msg.command](self, msg)
				elif msg.command in self.msg:
					self.msg[msg.command](self, msg)
		mainthread.join()
		self.sock = None


class text(object):
	
	@staticmethod
	def stripansi(text):
		pass
		r_bold = re.compile(r"\x02", re.UNICODE)
		r_color = re.compile(r"\x03(?:[0-9]{1,2}(?:[0-9]{1,2})?)?", re.UNICODE)
		r_origin = re.compile(r"\x0f", re.UNICODE)
		r_reverse = re.compile(r"\x16", re.UNICODE)
		r_under = re.compile(r"\x1f", re.UNICODE)
		ext = text
		ext = r_bold.sub("", ext)
		ext = r_color.sub("", ext)
		ext = r_origin.sub("", ext)
		ext = r_reverse.sub("", ext)
		ext = r_under.sub("", ext)
		return ext

	@staticmethod
	def bold(text):
		#2
		return chr(2) + text + chr(2)

	@staticmethod
	def color(text, color, bg=None):
		#3
		ext = chr(3) + "{:02d}".format(color)
		if bg is not None:
			ext += ",{:02d}".format(color)
		ext += text + chr(3)
		return ext

	@staticmethod
	def origin():
		#15
		return chr(15)

	@staticmethod
	def reverse(text):
		#22
		return chr(22) + text + chr(22)

	@staticmethod
	def under(text):
		#31
		return chr(31) + text + chr(31)


def atia(*args): # array to irc args
	ext = []
	for arg in args:
		if u" " in arg:
			ext.append(u":" + arg)
			break
		else:
			ext.append(arg)
	return ext

def stia(text): # string to irc args
	ext = []
	s = text.split(u" ")
	i = -1
	for w in s:
		i += 1
		if w.startswith(u":"):
			ext.append(u" ".join(s[i:]))
			break
		else:
			ext.append(w)
	return ext

def atias(*args): # array to irc args string
	a = atia(*args)
	return " ".join(a)

def iata(*args): # irc args to array
	ext = []
	for arg in args:
		if arg.startswith(u":"):
			ext.append(arg[1:])
			break
		else:
			ext.append(arg)
	return ext
