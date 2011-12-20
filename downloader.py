import urllib
import urllib2
import cookielib
import re
import xml.dom.minidom
import os
import settings # This file should contain your DDI email and password
                # Or comment this import out and define settings.email and settings.password in this file
from BeautifulSoup import BeautifulSoup



cj = cookielib.CookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    

def login(category,item):
    loginUrl = build_login_url(category,item)
    print("Attempting to login with email : %s " % settings.email)
    resp = opener.open(loginUrl)
    page = resp.read()
    m = re.search("id=\"__VIEWSTATE\" value=\"([a-zA-Z0-9=+/]*)\"",page)
    viewstate = m.group(1)
    m = re.search("id=\"__EVENTVALIDATION\" value=\"([a-zA-Z0-9=+/]*)\"",page)
    eventvalidation = m.group(1)
    login_data = urllib.urlencode({'email' : settings.email, 'password' : settings.password, '__VIEWSTATE' : viewstate, '__EVENTVALIDATION' : eventvalidation, 'InsiderSignin' : 'Sign In'})
    resp = opener.open(loginUrl, login_data)
    
    

def logged_in(page):
    """Check to see if a returned page is the login page"""
    m = re.search("<input type=\"submit\" name=\"InsiderSignin\" value=\"Sign In\" id=\"InsiderSignin\" />",page)
    if not m:
        return True
    return False

def retrieve_page(category,item):
    url = build_url(category,item)
    response = opener.open(url)
    page = response.read()
    if not logged_in(page):
        login(category,item)
        return retrieve_page(category,item)
    return page

def retrieve_index(url):
    response = opener.open(url)
    page = response.read()

    return page

def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
        return ''.join(rc)

def handleClass(cclass):
    handleName(cclass.getElementsByTagName("Name")[0])
    handleID(cclass.getElementsByTagName("ID")[0])

def getNodeText(node,name):
    return getText(node.getElementsByTagName(name)[0].childNodes)
    

def index(path):
    print "Retrieving %s index" % path
    classurl = "http://www.wizards.com/dndinsider/compendium/CompendiumSearch.asmx/ViewAll?tab=" + path
    response = opener.open(classurl)
    print "Page retrieved"

    doc = xml.dom.minidom.parse(response)

    index = {}
    for node in doc.getElementsByTagName(path):
        Name = getNodeText(node,"Name")
        ID = int(getNodeText(node,"ID"))
        index[ID] = Name

    return index


def build_url(category,item):
    url = "http://www.wizards.com/dndinsider/compendium/display.aspx?page=%s&id=%s" % (category, item)
    return url

def build_login_url(category,item):
    url = "http://www.wizards.com/dndinsider/compendium/login.aspx?page=%s&id=%s" % (category, item)
    return url

def save_page(page,category,item):
    filename = "%s\%s.html" % (category, item)
    dirs = os.path.dirname(filename)
    if not os.path.exists(dirs):
        os.makedirs(dirs)
    f = open(filename,"w")
    f.write(page)
    f.close()

def save_file(url):
    if full_url(url):
        if re.match("http://www.wizards.com/dndinsider/compendium/",url):
            path = re.sub("http://www.wizards.com/dndinsider/compendium/","",url)
        elif re.match("http://www.wizards.com/dnd/",url):
            path = re.sub("http://www.wizards.com/dnd/","",url)
    else:
        path = url
        url = "http://www.wizards.com/dndinsider/compendium/%s" % path
    if not os.path.exists(path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        resp = opener.open(url)
        print "Saving file : %s " % path
        f = open(path,"wb")
        f.write(resp.read())
        f.close()

def strip_urls(url):
    if re.match('http://www.wizards.com/dndinsider/compendium/',url):
        return re.sub('http://www.wizards.com/dndinsider/compendium/','',url)
    elif re.match('http://www.wizards.com/dnd/',url):
        return re.sub('http://www.wizards.com/dnd/','',url)
    print "I do not know how to strip this url : %s" % url
    return url

def cleanup_page(page):
    soup = BeautifulSoup(page)
    for script in soup.findAll(name='script'):
        script.extract()
    soup.meta.extract()
    soup.input.extract()
    link = soup.link
    for link in soup.findAll(name='link'):
        save_file(link['href'])
        if full_url(link['href']):
            link['href'] = strip_urls(link['href'])         
        link['href'] = "../" + link['href']
    for image in soup.findAll(name='img'):
        save_file(image['src'])
        if full_url(image['src']):
            image['src'] = strip_urls(image['src'])
        image['src'] = "../" + image['src']
    page = soup.prettify()
    page = re.sub('\xe2\x80\x99',"'",page)
    page = re.sub('\xe2\x80\x94','&#8212;',page)
    return page

def full_url(string):
    if re.match("http",string):
        return True
    return False
    

def crawl_category(category,failed):
    ind = index(category)
    for item in ind:
        print "Retrieving %s %s: %s" % (category, item, ind[item])
        try:
            page = retrieve_page(category,item)
        except urllib2.HTTPError:
            if category == "Companion":
                try:
                    #Some "Companions" are "Associates"
                    page = retrieve_page("Associate",item)
                except urllib2.HTTPError:
                    print "Failed on retry: %s %s" % ("Associate",item)
                    failed.append((category,item))
                    continue
            else:
                print "Failed: %s %s" % (category,item)
                failed.append((category,item))
                continue
        page = cleanup_page(page)
        save_page(page,category,item)
    return failed

def download_styles():
    urls = ['http://www.wizards.com/dndinsider/compendium/styles/site.css',
            'http://www.wizards.com/dndinsider/compendium/styles/detail.css',
            'http://www.wizards.com/dndinsider/compendium/styles/mobile.css',
            'http://www.wizards.com/dndinsider/compendium/styles/print.css',
            'http://www.wizards.com/dndinsider/compendium/styles/reset.css']
    # Hack for now, eventually parse CSS files to generate list of required stylesheets.
    for url in urls:
        save_file(url)

download_styles()
        
categories = ['Class', 'Companion', 'Deity', 'Disease',
              'EpicDestiny', 'Feat', 'Glossary', 'Item',
              'Monster', 'ParagonPath', 'Poison', 'Power',
              'Race', 'Ritual', 'Skill', 'Terrain']

failed = []

for category in categories:
    failed = crawl_category(category,failed)
    
print failed
