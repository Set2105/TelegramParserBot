import telebot
import json
import traceback
import threading
import time
from classes import User, ParsedUrl, ChromeDriver
from constants import USERS_DIR, URLS_DIR, BOT_TOKEN, TIMEOUT_CHECKING
import os


bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

bot_users = []
users_steak = {}

urls_to_listen = {}

driver = ChromeDriver()


def load_users():
    for json_file in os.listdir(USERS_DIR):
        with open(os.path.join(USERS_DIR, json_file), 'r') as file:
            text = ''
            for a in file:
                text += a
        data = json.loads(text)
        bot_users.append(data['telegram_id'])
        users_steak.update({data['telegram_id']: {'is_listening': False}})


def load_links():
    for json_file in os.listdir(URLS_DIR):
        p_url = ParsedUrl(driver=driver)
        try:
            p_url.load_from_json(json_path=os.path.join(URLS_DIR, json_file))
            urls_to_listen.update({p_url.id: p_url})
        except Exception as e:
            traceback.format_exc()


load_links()
load_users()


def create_start_menu():
    markup = telebot.types.InlineKeyboardMarkup()
    item_btn_list = telebot.types.InlineKeyboardButton(text='Список Активных ссылок', callback_data=json.dumps({"command": "list"}))
    itembtn_add_url = telebot.types.InlineKeyboardButton(text='Добавить ссылку', callback_data=json.dumps({"command": "add_url"}))
    markup.row(item_btn_list, itembtn_add_url)
    return markup


def create_url_markup(url_id):
    markup = telebot.types.InlineKeyboardMarkup()
    item_btn_delete = telebot.types.InlineKeyboardButton(text='Удалить', callback_data=json.dumps(
        {"command": "delete_url", "id": url_id}))
    item_btn_rename = telebot.types.InlineKeyboardButton(text='Изменить Название', callback_data=json.dumps(
        {"command": "update_url", "id": url_id, 'arg_to_change': 'name'}))
    item_btn_rewrite = telebot.types.InlineKeyboardButton(text='Изменить Ссылку', callback_data=json.dumps(
        {"command": "update_url", "id": url_id, 'arg_to_change': 'url'}))
    item_btn_rewrite_words = telebot.types.InlineKeyboardButton(text='Изменить Проверочные слова', callback_data=json.dumps(
        {"command": "update_url", "id": url_id, 'arg_to_change': 'words'}))
    markup.row(item_btn_rename, item_btn_rewrite, item_btn_rewrite_words)
    markup.row(item_btn_delete)
    return markup


start_menu_markup = create_start_menu()


def get_all_user_urls(user_id):
    result = []
    for url in urls_to_listen.values():
        if url.user == user_id:
            result.append(url)
    return result


class IsLogged(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_logged'

    @staticmethod
    def check(message: telebot.types.Message):
        return message.from_user.id in bot_users


class IsListening(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_listening'

    @staticmethod
    def check(message: telebot.types.Message):
        try:
            return users_steak[message.from_user.id]['is_listening']
        except Exception as e:
            print(traceback.format_exc())
            return False


bot.add_custom_filter(IsLogged())
bot.add_custom_filter(IsListening())


def add_url(values, user_id):
    print(values)
    values = values['value']
    name = values[0]
    url = values[1]
    words = values[2].strip('\'')
    words = words.split('\' \'')
    url_to_parse = ParsedUrl(user=user_id, name=name, url=url, driver=driver, words=words)
    url_to_parse.save_json()
    urls_to_listen.update({url_to_parse.id: url_to_parse})


def update_url(values, user_id):
    arg_to_change = values['arg_to_change']
    url_id = values['id']
    value = values['value'][0]

    url = urls_to_listen[url_id]
    if url.user == user_id:
        if arg_to_change == 'name':
            url.update(name=value)
        elif arg_to_change == 'url':
            url.update(url=value)
        elif arg_to_change == 'words':
            words = value.strip('\'')
            words = words.split('\' \'')
            url.update(words=words)


@bot.message_handler(commands=['help', 'start'], is_listening=False)
def send_welcome(message):
    if message.from_user.id not in bot_users:
        bot.send_message(message.chat.id, "Введите:\n /login 'Логин' 'Пароль'\nчтобы войти")
    else:
        bot.send_message(message.chat.id,
                         "/list - список проверяемых ссылок и их статус\n"
                         "/add_url - добавить ссылку для парсинга\n",
                         reply_markup=start_menu_markup)


@bot.message_handler(commands=['list'], is_listening=False, is_logged=True)
def list_url(message):
    urls_list = get_all_user_urls(message.from_user.id)
    if not len(urls_list):
        bot.send_message(message.from_user.id, 'Список ссылок пуст !', reply_markup=start_menu_markup)
    else:
        for url in get_all_user_urls(message.from_user.id):
            bot.send_message(message.from_user.id, '{}\n{}\nПроверочные слова:{}\nСтатус:{}\n'.format(url.name, url.url, url.words, url.current_word,disable_web_page_preview=True), reply_markup=create_url_markup(url.id))


@bot.message_handler(commands=['login'], is_logged=False)
def login(message):
    try:
        message_text = message.text.strip('/login ')
        login, password = message_text.split()
        json_path = os.path.join(USERS_DIR, '{}.json'.format(login))
        user = User()
        user.load_from_json(json_path)
        if user.password == password:
            user.telegram_id = message.from_user.id
            user.save_json()
            bot_users.append(user.telegram_id)
            users_steak.update({message.from_user.id: {'is_listening': False}})
            bot.send_message(message.chat.id, '{}, вы успешно залогинились!\nвведите /help, чтобы увидеть все команды бота'.format(message.from_user.username))
        else:
            bot.send_message(message.chat.id, 'Логин или пароль неверeн !')
    except Exception as e:
        print(traceback.format_exc())
        bot.send_message(message.chat.id, 'Логин или пароль неверeн !')


@bot.message_handler(commands=['add_url'], is_logged=True, is_listening=False)
def add_url_stack(message):
    users_steak[message.from_user.id].update(
                {
                    'steak':
                    [
                        'Введите название ссылки',
                        'Введите ссылку',
                        'Введите слова для поиска в виде:\n\'выражение один\' \'выражение два\' \'выражение три\'',
                    ],
                    'values': {'value': []},
                    'function': add_url,
                    'success_message': 'Успешно добавлено',
                    'fail_message': 'Ошибка добавления',
                    'is_listening': True
                }
        )
    bot.send_message(message.chat.id, users_steak[message.from_user.id]['steak'].pop(0))


@bot.message_handler(is_listening=True)
def steak(message):
    dct = users_steak[message.from_user.id]
    dct['values']['value'].append(message.text)
    if not (len(dct['steak']) == 0):
        bot.send_message(message.chat.id, dct['steak'].pop(0))
    else:
        try:
            dct['function'](dct['values'], message.from_user.id)
            bot.send_message(message.chat.id, dct['success_message'])
            dct['is_listening'] = False
        except Exception as e:
            print(e)
            traceback.format_exc()
            bot.send_message(message.chat.id, dct['fail_message'])
            dct['is_listening'] = False


@bot.message_handler(commands=['test_btn'], is_logged=True, is_listening=False)
def test_btn(message):
    markup = telebot.types.InlineKeyboardMarkup()
    itembtnc = telebot.types.InlineKeyboardButton(text='a', callback_data=json.dumps({"text": "text", "args": [1, 2, 3]}))
    itembtna = telebot.types.InlineKeyboardButton(text='list', callback_data=json.dumps({"command": "list"}))
    markup.row(itembtnc, itembtna)
    print(bot.send_message(message.chat.id, "<a hreaf=\"/list\">list</a>", reply_markup=markup))


@bot.callback_query_handler(func=lambda callback: True)
def test(callback):

    data = json.loads(callback.data)
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    print(data, chat_id, user_id)

    if data['command'] == "list":
        urls_list = get_all_user_urls(user_id)
        if not len(urls_list):
            bot.send_message(user_id, 'Список ссылок пуст !', reply_markup=start_menu_markup)
        else:
            for url in get_all_user_urls(user_id):
                bot.send_message(user_id, '{}\n{}\nПроверочные слова:{}\nСтатус:{}\n'.format(url.name, url.url, url.words, url.current_word,disable_web_page_preview=True), reply_markup=create_url_markup(url.id))

    if data['command'] == 'add_url':
        users_steak[user_id].update(
                {
                    'steak':
                    [
                        'Введите название ссылки',
                        'Введите ссылку',
                        'Введите слова для поиска в виде:\n\'выражение один\' \'выражение два\' \'выражение три\'',
                    ],
                    'values': {'value': []},
                    'function': add_url,
                    'success_message': 'Успешно добавлено',
                    'fail_message': 'Ошибка добавления',
                    'is_listening': True
                }
        )
        bot.send_message(chat_id, users_steak[user_id]['steak'].pop(0))

    if data['command'] == "delete_url":
        url_id = data['id']
        try:
            if url_id in urls_to_listen.keys():
                url_to_delete = urls_to_listen[url_id]
                if url_to_delete.user == user_id:
                    url_to_delete = urls_to_listen.pop(url_id)
                    url_to_delete.__del__()
                    bot.send_message(chat_id, "Успешно удалено !")
                else:
                    bot.send_message(chat_id, "Нет прав на удаление !")
            else:
                bot.send_message(chat_id, "Ссылка не найдена !")
        except Exception as e:
            traceback.format_exc()
            bot.send_message(chat_id, "Ошибка удаления !")

    if data['command'] == "update_url":
        url_id = data['id']
        arg_to_change = data['arg_to_change']

        users_steak[user_id].update(
            {
                'steak':
                    [
                        'Введите новое значение:',
                    ],
                'values': {'value': [], 'id': url_id, 'arg_to_change': arg_to_change},
                'function': update_url,
                'success_message': 'Успешно изменено',
                'fail_message': 'Ошибка изменения',
                'is_listening': True
            }
        )
        bot.send_message(chat_id, users_steak[user_id]['steak'].pop(0))


def start_bot():
    while True:
        try:
            bot.polling()
        except Exception as e:
            traceback.format_exc()


def start_parser():
    while True:
        try:
            for link in urls_to_listen.values():
                text = link.check()
                if text:
                    bot.send_message(link.user, text)
                    if link in urls_to_listen.values():
                        link.save_json()
            driver.driver.close()
            driver.driver = False
            time.sleep(TIMEOUT_CHECKING)
        except Exception as e:
            traceback.format_exc()


t1 = threading.Thread(target=start_bot)
t2 = threading.Thread(target=start_parser)

t1.start()
t2.start()