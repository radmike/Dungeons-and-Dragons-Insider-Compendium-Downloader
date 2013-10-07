import urllib
import urllib2
import cookielib
import codecs
import re
import os
import settings # This file should contain your DDI email and password
                # Or comment this import out and define settings.email and settings.password in this file
from BeautifulSoup import BeautifulSoup

class LoginError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class DDIDownloader:

	meta = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>\n'

	loginurl   = "http://www.wizards.com/dndinsider/compendium/login.aspx?page=%s&id=%s"
	displayurl = "http://www.wizards.com/dndinsider/compendium/display.aspx?page=%s&id=%s"
	indexurl   = "http://www.wizards.com/dndinsider/compendium/CompendiumSearch.asmx/ViewAll?tab="
	stripurls = ["http://www.wizards.com/dndinsider/compendium/",
				 "http://www.wizards.com/dnd/"]
				 
	compendium_dir = "compendium/"

	loginattempts = 0
	maxloginattempts = 5

	categories  = 	['Background', 'Class', 'Companion', 'Deity', 'Disease',
					'EpicDestiny', 'Feat', 'Glossary', 'Item',
					'Monster', 'ParagonPath', 'Poison', 'Power',
					'Race', 'Ritual', 'Terrain', 'Trap']

	fields	=  	[['type','campaign','skills'],
				['powersourcetext','rolename','keyabilities'],
				['type'],
				['alignment'],
				['level'],
				['prerequisite'],
				['tiername','tiersort'],
				['category','type'],
				['cost','level','rarity','category','levelsort','costsort'],
				['level','grouprole','combatrole'],
				['prerequisite'],
				['level','cost'],
				['level','actiontype','classname'],
				['descriptionattribute'],
				['componentcost','price','keyskilldescription'],
				['type'],
				['grouprole','type','level']]
	for i in fields:
		i.insert(0,'name')
		i.insert(0,'id')
		i.append('sourcebook')

	downloadqueue = []
	failed = []

	cj = cookielib.CookieJar()
	opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
	open = opener.open
	email = ""
	password = ""

	def __init__(self, email, password):
		self.email = email
		self.password = password

	def login(self,category,item):
		"""This logs into the DDI"""
		loginUrl = self.build_url(self.loginurl,category,item)
		print("Attempting to login with email : %s " % self.email)
		"""First we acquire the __VIEWSTATE and __EVENTVALIDATION variables
		These seem to be neccessary to log in successfully"""
		resp = self.open(loginUrl)
		page = resp.read()
		m = re.search("id=\"__VIEWSTATE\" value=\"([a-zA-Z0-9=+/]*)\"",page)
		viewstate = m.group(1)
		m = re.search("id=\"__EVENTVALIDATION\" value=\"([a-zA-Z0-9=+/]*)\"",page)
		eventvalidation = m.group(1)
		#Build the login variable string
		login_data = urllib.urlencode({'email' : self.email, 'password' : self.password, '__VIEWSTATE' : viewstate, '__EVENTVALIDATION' : eventvalidation, 'InsiderSignin' : 'Sign In'})
		resp = self.open(loginUrl, login_data)

	def logged_in(self,page):
		"""Check to see if a returned page is the login page"""
		m = re.search("<input type=\"submit\" name=\"InsiderSignin\" value=\"Sign In\" id=\"InsiderSignin\" />",page)
		if not m:
			return True
		return False

	def retrieve_page(self,category,item):
		"""Retrieve a given DDI page labelled by category and ID"""
		url = self.build_url(self.displayurl,category,item)
		response = self.open(url)
		page = response.read()
		if not self.logged_in(page):
			self.loginattempts += 1
			if self.loginattempts > self.maxloginattempts:
				raise LoginError("Reached Maximum Login Attempts")
			self.login(category,item)
			return self.retrieve_page(category,item)
		return page

	def index(self,category):
		classurl = self.indexurl + category
		response = self.open(classurl)
		
		soup = BeautifulSoup(response)
		
		index = {}
		D.soup = soup
		for node in soup.findAll(category.lower()):
			name = node.find("name").text
			id = int(node.find("id").text)
			index[id] = name
		return index

	def build_url(self,baseurl,category,item):
		url = baseurl % (category, item)
		return url

	def save_page(self,page,category,item):
		filename = os.path.join(self.compendium_dir, category, "%s.html" % (item))
		dirs = os.path.dirname(filename)
		if not os.path.exists(dirs):
			os.makedirs(dirs)
		f = codecs.open(filename,"w",'utf-8')
		f.write(page.decode('utf-8'))
		f.close()

	def full_url(self,string):
		if re.match("http",string):
			return True
		return False

	def save_file(self,url):
		if self.full_url(url):
			path = self.strip_urls(url)
		else:
			path = url
			url = "http://www.wizards.com/dndinsider/compendium/%s" % path
			
		path = self.compendium_dir + path
		
		if not os.path.exists(path):
			dirname = os.path.dirname(path)
			if not os.path.exists(dirname):
				os.makedirs(dirname)
			resp = self.open(url)
			print "Saving file : %s " % path
			f = open(path,"wb")
			f.write(resp.read())
			f.close()

	def save_xml(self,page,category):
		path = self.compendium_dir + "%s.xml" % category
		if not os.path.exists(path):
			print "Saving file : %s " % path
			f = open(path,"w")
			f.write(page)
			f.close()

	def strip_urls(self,url):
		for urlroot in self.stripurls:
			if re.match(urlroot,url):
				return re.sub(urlroot,"",url)
		print "I do not know how to strip this url : %s" % url
		return url

	def cleanup_page(self,page):
		soup = BeautifulSoup(page)
		for script in soup.findAll(name='script'):
			script.extract()
		soup.meta.extract()
		soup.input.extract()
		link = soup.link
		for link in soup.findAll(name='link'):
			self.save_file(link['href'])
			if self.full_url(link['href']):
				link['href'] = self.strip_urls(link['href'])
			link['href'] = "../" + link['href']
		for image in soup.findAll(name='img'):
			self.save_file(image['src'])
			if self.full_url(image['src']):
				image['src'] = self.strip_urls(image['src'])
			image['src'] = "../" + image['src']
		page = soup.prettify()
		page = self.meta + page
		return page

	def crawl_category(self,category):
		ind = self.index(category)
		for item in ind:
			print "Retrieving %s %s: %s" % (category, item, ind[item].encode('utf-8'))
			try:
				page = self.retrieve_page(category,item)
			except urllib2.HTTPError:
				if category == "Companion":
					try:
						#Some "Companions" are "Associates"
						page = self.retrieve_page("Associate",item)
					except urllib2.HTTPError:
						print "Failed on retry: %s %s" % ("Associate",item)
						failed.append((category,item))
						continue
				else:
					print "Failed: %s %s" % (category,item)
					self.failed.append((category,item))
					continue
			page = self.cleanup_page(page)
			self.save_page(page,category,item)

	def download_styles(self):
		urls = ['http://www.wizards.com/dndinsider/compendium/styles/site.css',
				'http://www.wizards.com/dndinsider/compendium/styles/detail.css',
				'http://www.wizards.com/dndinsider/compendium/styles/mobile.css',
				'http://www.wizards.com/dndinsider/compendium/styles/print.css',
				'http://www.wizards.com/dndinsider/compendium/styles/reset.css']
		# Hack for now, eventually parse CSS files to generate list of required stylesheets.
		for url in urls:
			self.save_file(url)

	def download_files(self):
		for category in self.categories:
			self.crawl_category(category)

	def create_index_html(self):
		for category in self.categories:
			classurl = self.indexurl + category
			response = self.open(classurl)
			print "Obtained %s index" % category
			soup = BeautifulSoup(response)
			variables = []
			for node in soup.findAll(category.lower()):
				nodevars = []
				for type in self.fields[self.categories.index(category)]:
					nodevars.append(node.find(type).text)
				variables.append(nodevars)
				
			index = self.meta + "<html><body>"
			for item in variables:
				url = "%s/%s.html" % (category , item[0])
				name = item[1]
				link = "\n\t<br /><a href='%s'>%s</a>" % (url,name)
				index += link
			index += "\n</html></body>"

			path = self.compendium_dir + ("%s.html" % category)
			if not os.path.exists(path):
				dirname = os.path.dirname(path)
				if not os.path.exists(dirname):
					os.makedirs(dirname)
			print "Saving index file : %s " % path
			f = codecs.open(path,"w",'utf-8')
			f.write(index)
			f.close()

D = DDIDownloader(settings.email,settings.password)
D.create_index_html()
D.download_styles()
D.download_files()
