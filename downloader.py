import urllib2
import re
import os
import subprocess
import imp

from BeautifulSoup import BeautifulSoup

from settings import DOWNLOADS_FOLDER, PROGRAM_PATH
from utils import remove_html_tags, remove_entities
from errors import DownloaderError

class Downloader(object):
    def __init__(self):
        #identify the trackers we can use that exist in the trackers folder
        self._trackers = self._get_trackers()

    def _get_trackers(self):
        """Loads tracker files and populates a dict with them"""
        trackers_path = os.path.join(PROGRAM_PATH, 'trackers')
        files = os.listdir(trackers_path)
        tracker_files = [file for file in files if file[-4:] != '.pyc' and file != '__init__.py']
        trackers = []
        for tracker in tracker_files:
            tracker_name = tracker.replace('.py', '')
            trackers.append(tracker_name)
        return trackers

    def download(self, search_term, desired_item_name):
        """Tries to download something with the desired_item_name from the torrentz results after searching for search_term"""
        #TODO: make this a general search call that can take any search site
        #search_results is BeautifulSoup of torrentz.com
        search_results = self._torrentz_search(search_term)
        try:
            #results from tracker meta-search
            parsed_general_results =  self._parse_general_search(search_results)
            #identifies the item we want to download
            desired_link = self._general_result_link(parsed_general_results, desired_item_name)
            #identifies trackers with desired item
            tracker_results = self._find_trackers(desired_link)
            #downloads .torrent file of item to file_path
            file_path = self._download_torrent_file(search_term, desired_item_name, tracker_results)
            self._open_torrent(file_path)
        except DownloaderError as error:
           print 'Unable to download -- %s' % str(error)
        return 0

    def _download_torrent_file(self, search_term, desired_item_name, tracker_results):
        ''''Uses wget to download a .torrent file'''
        downloaded = False
        for tracker_name, tracker_url in tracker_results.items():
            if not downloaded:
                base_file_path = DOWNLOADS_FOLDER
                file_path = base_file_path + desired_item_name.replace(' ', '') + '.torrent'
                print 'Downloading from', '%s...' % tracker_name
                tracker_file = tracker_name + ".py"
                tracker_path = os.path.join(PROGRAM_PATH, 'trackers', tracker_file)
                source = imp.load_source('find_url', tracker_path)
                find_url = source.find_url
                #url is the actual torrent's url on the tracker's site
                url = find_url(tracker_url, PROGRAM_PATH)
                if url:
                    wget_result = os.system('wget -O "%s" "%s" -t 2 -T 5' % (file_path, url))
                    if wget_result == 0:
                        downloaded = True
        if downloaded:
            return file_path
        else:
            raise DownloaderError('Unable to download from any tracker')

    def _torrentz_search(self, search_term):
        """Searches for search_term on torrentz.com and returns the soup that results."""
        search_term = search_term.lower()
        split_term = search_term.split()
        url = 'http://www.torrentz.com/feed?q='
        for word in split_term:
            url += word + '+'
        url = url[:-1]
        sock = urllib2.urlopen(url)
        html = sock.read()
        sock.close()
        soup = BeautifulSoup(html)
        return soup

    def _parse_general_search(self, search_results):
        '''Finds the item to download from meta-search results'''
        parsed_results = {}
        for item in search_results('item'):
            description = str(item.description)
            seeds_index = description.index('Seeds') + 7
            cut_description = description[seeds_index:]
            space_index = cut_description.index(' ')
            seeds = cut_description[:space_index]
            seeds = seeds.replace(",", "")
            seeds = int(seeds)
            if 'flac' not in str(item.category).lower() and 'wma' not in str(item.category).lower() and seeds >= 5:
                title = item.title
                title = remove_html_tags(str(title))
                title = remove_entities(title)
                #guid is the url of the 'choose a tracker' page on torrentz
                guid = item.guid
                guid = remove_html_tags(str(guid))
                parsed_results[title] = guid
        if parsed_results == {}:
            raise DownloaderError('No valid results for search term')
        return parsed_results

    def _general_result_link(self, parsed_general_results, desired_item_name):
        """Returns a url for the 'choose a tracker' page on torrentz"""
        for name, link in parsed_general_results.items():
            if desired_item_name.lower() in name.lower():
                return link
        raise DownloaderError('Desired item not in search results')

    def _find_trackers(self, secondary_results_link, attempts=0):
        '''Identifies trackers that have the file that we can download from'''
        found_trackers = {}
        if attempts < 3:
            try:
                sock = urllib2.urlopen(secondary_results_link)
                html = sock.read()
                sock.close()
            except urllib2.URLError:
                attempts += 1
                found_trackers = self._find_trackers(secondary_results_link, attempts)
            soup = BeautifulSoup(html)
            #all possible links on the page
            possible_trackers = soup.findAll('a')
            for possible_tracker in possible_trackers:
                tracker = remove_html_tags(str(possible_tracker)).split()
                if tracker:
                    #tracker[0] is the name of the tracker
                    tracker = tracker[0].replace('.com', '')
                    if tracker in self._trackers:
                        #link is "href="http://whatever.com"
                        link = str(possible_tracker).split()[1]
                        first_quote = link.index('"') + 1
                        second_quote = link.index('"', first_quote)
                        link = link[first_quote:second_quote]
                        #now link is just url of tracker
                        found_trackers[tracker] = link
        if found_trackers == {}:
            raise DownloaderError('No known trackers')
        return found_trackers

    def _open_torrent(self, file_path):
        if os.name == 'posix':
            subprocess.call(('open', file_path))
        elif os.name == 'nt':
            subprocess.call(('start', file_path))
        return 0
