import json
import logging
import time
from threading import Thread

import hashlib
import requests

import bot.connectivity.haiku_parser as parser
import config


def make_urls():
    flat_list = []
    url = config.STASH_URL if config.STASH_URL[len(config.STASH_URL) - 1] == '/' else config.STASH_URL + '/'
    for project in config.STASH_REPOSITORIES:
        for repo in project['REPOSITORIES']:
            flat_list.append(
                "{}rest/api/1.0/projects/{}/repos/{}/pull-requests".format(url, project['REPO_KEY'], repo)
            )

    logging.debug('URLs configured: ' + str(flat_list))
    return flat_list


def faux_response(url):
    return json.loads(open(config.DEBUG_URL, 'r').read())


class Stash(Thread):
    def __init__(self, post_func, store):
        Thread.__init__(self)
        self.alive = False
        self.post_func = post_func
        self.store = store
        self.urls = make_urls()

        if config.DEBUG:
            logging.critical('config.DEBUG is set, serving file instead of GET requests')
            self.fetch = faux_response  # Override get so we can serve a file

    def run(self):
        while self.alive:
            for url in self.urls:
                try:
                    result = self.fetch(url)
                except OSError:
                    logging.error('Server not responding: ' + url)
                    continue

                url_id = hashlib.md5(url.replace('?state=MERGED', '').encode('utf-8')).hexdigest()
                parsed = parser.parse_stash_response(result, url_id, self.store)

                for haiku in parsed:
                    self.post_func(haiku['haiku'], haiku['author'], haiku['link'])

            if self.alive:
                for _ in range(config.STASH_POLL_TIME):
                    time.sleep(1)

    def start(self, live=True):
        self.alive = live
        Thread.start(self)

    def fetch(self, url):
        response = requests.get(url, headers=config.STASH_HEADERS, verify=config.SSL_VERIFY)
        return json.loads(response.text)

    def stop(self):
        self.alive = False

    def is_alive(self):
        return self.alive
