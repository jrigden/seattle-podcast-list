# The MIT License (MIT)

# Copyright (c) 2019 Jason Rigden

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import datetime
import os.path
import re
import urllib.request

from pyPodcastParser.Podcast import Podcast

from bs4 import BeautifulSoup
import feedparser
from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageFile
import requests
import requests_cache
from slugify import slugify

import config

requests_cache.install_cache()



file_loader = FileSystemLoader('templates')
env = Environment(loader=file_loader)

deadline = datetime.datetime.now() - datetime.timedelta(days=90)
active_categories = []
keywords = []
podcasts = []

feeds_with_no_links = []
feeds_with_no_title = []
feeds_with_failed_cover_art = []



def generate_cover_art(podcast):
    cover_art_dir = config.DATA['OUTPUT_DIR']  + "cover_art/"
    size = 150, 150
    file_name = cover_art_dir + podcast.cover_art
    if os.path.isfile(file_name):
        print("   already have image")
        return
    req = urllib.request.Request(
        podcast.itune_image, 
        data=None, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    )
    f = urllib.request.urlopen(req)
    image = Image.open(f)
    image = image.convert('RGB')
    image.thumbnail(size)
    image.save(file_name, "JPEG", optimize=True)
    




def better_sortable_text(text):
    text = text.lower().strip()
    text = remove_article(text)
    return text

def remove_article(text):
    articles = ["the ", "a ", "an "]
    for article in articles:
        if text.startswith(article):
            text = text[len(article):]
    return text

def alphabetize_podcasts(podcasts):
    alphabetizes_podcasts = sorted(podcasts, key=lambda x: x.better_sortable_title)
    return alphabetizes_podcasts

def is_podcast_active(podcast):
    sorted_items = sorted(podcast.items, key=lambda x: x.date_time, reverse=True)
    try:
        if deadline > sorted_items[0].date_time:
            return False
        else:
            return True
    except IndexError:
        return False


def divide_active_and_inactive(podcasts):
    active = []
    inactive = []
    for podcast in podcasts:
        if is_podcast_active(podcast):
            active.append(podcast)
        else:
            inactive.append(podcast)
    return alphabetize_podcasts(active), alphabetize_podcasts(inactive)


##  Jinja2 Stuff

def generate_index():
    active_podcasts, inactive_podcasts = divide_active_and_inactive(podcasts)
    message = "The Seattle Podcast List"
    template = env.get_template('index.html')
    output = template.render(DATA=config.DATA, active_podcasts=active_podcasts, inactive_podcasts=inactive_podcasts, message=message)
    file_path = config.DATA['OUTPUT_DIR']  + "index.html"
    with open(file_path, 'w') as f:
        f.write(output)

def generate_category_list():
    blocked_category = ["-- None --"]
    for category in active_categories:
        if category in blocked_category:
            active_categories.remove(category)
    #print(active_categories)
    categories = list(set(active_categories))
    categories = [i for i in categories if i] 
    categories.sort()
    categories_slugs = []
    for each in categories:
        categories_slugs.append(slugify(each))
    file_path = config.DATA['OUTPUT_DIR']  + "categories/index.html"
    template = env.get_template('categories_list.html')
    output = template.render(DATA=config.DATA, categories=categories, categories_slugs=categories_slugs)
    with open(file_path, 'w') as f:
        f.write(output)
    


def category_filter(category):
    filtered_podcasts = []
    for podcast in podcasts:
        if category in podcast.itunes_categories:
            filtered_podcasts.append(podcast)
    return divide_active_and_inactive(filtered_podcasts)


def generate_category_pages():
    categories = list(set(active_categories))
    for each in categories:
        generate_category_page(each)


def generate_category_page(category):
    message = category
    active_podcasts, inactive_podcasts = category_filter(category)
    template = env.get_template('index.html')
    directory = config.DATA['OUTPUT_DIR']  + "categories/" + slugify(category)
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = directory + "/index.html"
    output = template.render(DATA=config.DATA, active_podcasts=active_podcasts, inactive_podcasts=inactive_podcasts, message=message)
    with open(file_path, 'w') as f:
        f.write(output)


def add_itunes_categories(categories):
    for each in categories:
        if not None:
            active_categories.append(each)

# def get_homepage(content):
#     soup = BeautifulSoup(content, "xml")
#     links = soup.find_all('link')
#     for link in links:
#         if str(link).startswith("<link>"):
#             return link.string





def print_report():
    print("These feeds seem to lack links")
    for each in feeds_with_no_links:
        print("    " + each)

    print("These feeds seem to have no title")
    for each in feeds_with_no_title:
        print("    " + each)

    print("These feeds seem to failed art")
    for each in feeds_with_failed_cover_art:
        print("    " + each)

with open(config.DATA['RSS_LIST_PATH']) as f:
    rss_urls = f.readlines()
rss_urls = [x.strip() for x in rss_urls]
rss_urls = list(set(rss_urls))

for rss_url in rss_urls:
    print(rss_url)
    response = requests.get(rss_url)
    podcast = Podcast(response.content)
    parsed_rss = feedparser.parse(response.content)

    try:
        podcast.homepage = parsed_rss['feed']['link']
    except KeyError:
        feeds_with_no_links.append(rss_url)
        continue
    podcast.rss_url = rss_url

    try:
        podcast.title = parsed_rss['feed']['title']
    except KeyError:
        feeds_with_no_title.append(rss_url)
        continue
    if not podcast.title:
        feeds_with_no_title.append(rss_url)
        continue

    if podcast.subtitle is None:
        podcast.subtitle = ""
    if podcast.summary is None:
        podcast.summary = ""

    
    podcast.better_sortable_title = better_sortable_text(podcast.title)
    podcast.cover_art = slugify(podcast.title) + ".jpeg"
    try:
        generate_cover_art(podcast)
    except:
        print("    cover art fail for " + podcast.title)
        feeds_with_failed_cover_art.append(rss_url)
        continue
    podcasts.append(podcast)
    add_itunes_categories(podcast.itunes_categories)






generate_index()
generate_category_pages()
generate_category_list()
print_report()
