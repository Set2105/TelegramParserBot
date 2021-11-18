from typing import List
import json
import os
import time
import datetime
import re
from constants import USERS_DIR, URLS_DIR,  WAIT_BEFORE_PARSING
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import traceback


def console_log(message, end='\n'):
    now = datetime.datetime.now()
    print("[{:02d}:{:02d}:{:02d}]: {}".format(now.hour, now.minute, now.second, message), end=end)


def find_max_id(path_dir):
    files = os.listdir(path_dir)
    id = 0
    for file in files:
        if int(file.split('.')[0]) > id:
            id = int(file.split('.')[0])
    return id


class User(object):

    listening_urls = []

    name = ''
    password = ''
    telegram_id = ''
    json_path = ''

    def __init__(self, name='', password='', telegram_id='', json_path=''):
        self.name, self.password, self.telegram_id, self.json_path = name, password, telegram_id, json_path

    def load_from_json(self, json_path):
        console_log('loading {}'.format(json_path))
        if json_path:
            with open(json_path, 'r') as json_file:
                file_text = ''
                for text in json_file:
                    file_text += text
                user_dict = json.loads(file_text)
                name, password, telegram_id = user_dict['name'], user_dict['password'], user_dict['telegram_id']
        self.name, self.password, self.telegram_id, self.json_path = name, password, telegram_id, json_path

    def save_json(self):
        console_log('saving {}'.format(self.json_path))
        with open(os.path.join(USERS_DIR, '{}.json'.format(self.name)), 'w') as json_file:
            json.dump({'name': self.name, 'password': self.password, 'telegram_id': self.telegram_id}, json_file)


class ChromeDriver(object):
    driver = False

    def create_driver(self):
        console_log('creating driver')
        options = Options()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome('chromedriver.exe', options=options)

    def get_text(self, url: str) -> str:
        if not self.driver:
            self.create_driver()

        self.driver.get(url)
        self.driver.refresh()

        time.sleep(WAIT_BEFORE_PARSING)

        text = self.driver.find_element(By.TAG_NAME, "BODY").text
        return text

    def find_words_in_url(self, url: str, words: List[str]) -> str:
        pure_text = self.get_text(url).lower()
        for word in words:
            if word.lower() in pure_text:
                return word
        return "Отсyтcтвyют совпадения"


class ParsedUrl(object):

    json_path = False
    current_word = ''

    def __init__(self, driver: ChromeDriver, user='', name='', url='',  words=[], json_path=False):
        self.words, self.url, self.driver, self.name, self.user, self.json_path = words, url, driver, name, user, json_path

    def load_from_json(self, json_path):
        console_log('loading {}'.format(json_path))
        if json_path:
            self.json_path = json_path
            with open(json_path, 'r') as json_file:
                file_text = ''
                for text in json_file:
                    file_text += text
                user_dict = json.loads(file_text)
                words, url, user, name, current_word, id = \
                    user_dict['words'], user_dict['url'], user_dict['user'], user_dict['name'], user_dict['current_word'], user_dict['id']
                self.current_word = current_word
        self.words, self.url, self.name, self.user, self.json_path, self.id = words, url, name, user, json_path, id

    def save_json(self):
        console_log('saving {}'.format(self.name), end=' ')
        if not self.json_path:
            try:
                self.id = find_max_id(URLS_DIR) + 1
            except Exception as e:
                print(traceback.format_exc())
                self.id = 0
            self.json_path = os.path.join(URLS_DIR, '{}.json'.format(self.id))
        with open(self.json_path, 'w') as json_file:
            print('to {}'.format(self.json_path))
            json.dump({'name': self.name, 'user': self.user, 'words': self.words, 'id': self.id, 'url':
                str(self.url), 'current_word':
                self.current_word}, json_file)

    def check(self):
        console_log('cheking {}'.format(self.name))

        try:
            checked_word = self.driver.find_words_in_url(self.url, self.words)
            if checked_word == self.current_word:
                return False
            else:
                text = '{}: Статус сменился с \"{}\" на \"{}\"'.format(self.name, self.current_word, checked_word)
                self.current_word = checked_word
                return text

        except Exception as e:
            traceback.format_exc()
            print(e.args)
            checked_word = 'Ошибкa зaгрузки стрaницы'
            if checked_word == self.current_word:
                return False
            else:
                self.current_word = checked_word
                return '{}: Ошибкa зaгрузки стрaницы'.format(self.name)

    def update(self, name="", words=[], url=""):
        to_save = False
        if name and name != self.name:
            self.name = name
            to_save = True
        if words:
            self.words = words
            to_save = True
        if url and url != self.url:
            self.url = url
            to_save = True
        if to_save:
            self.save_json()

    def __del__(self):
        if self.json_path:
            os.remove(self.json_path)
        del self
