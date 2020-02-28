import praw
import tweepy
import configparser
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import re
import string
import pickledb
import time
from bs4 import BeautifulSoup
from requests import get
import threading
from random import randint


print('Booting up...')

config = configparser.ConfigParser()
config.read('conf.ini')
reddit_user = config['REDDIT']['reddit_user']
reddit_pass = config['REDDIT']['reddit_pass']
reddit_client_id = config['REDDIT']['reddit_client_id']
reddit_client_secret = config['REDDIT']['reddit_client_secret']
target_subreddit = config['REDDIT']['target_subreddit']
twitter_consumer_key = config['TWITTER']['twitter_consumer_key']
twitter_consumer_secret = config['TWITTER']['twitter_consumer_secret']
twitter_access_token = config['TWITTER']['twitter_access_token']
twitter_access_token_secret = config['TWITTER']['twitter_access_token_secret']
telegram_api_key = config['TELEGRAM']['telegram_api_key']
telegram_admin = config['TELEGRAM']['telegram_admin']
telegram_admin = '@{}'.format(telegram_admin)

reddit = praw.Reddit(
    username=reddit_user,
    password=reddit_pass,
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent='TRT (by u/impshum)'
)

auth = tweepy.OAuthHandler(twitter_consumer_key, twitter_consumer_secret)
auth.set_access_token(twitter_access_token, twitter_access_token_secret)
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

id_db = pickledb.load('id_db.db', False)
kw_db = pickledb.load('kw_db.db', False)
h_db = pickledb.load('h_db.db', False)
bno_db = pickledb.load('bno_db.db', False)

keywords = []


def now():
    return int(time.time())


def get_date(epoch):
    return time.strftime("%d-%m-%Y %H:%M:%S", time.gmtime(epoch))


def history_dump(thing):
    if not h_db.exists(thing):
        h_db.set(thing, now())
        h_db.dump()


def get_keywords():
    keywords = []
    for x in kw_db.getall():
        keywords.append(x)
    return keywords


def id_set(thing):
    if not id_db.exists(thing):
        id_db.set(thing, now())
        id_db.dump()
        return True


def id_rem(thing):
    if id_db.exists(thing):
        id_db.rem(thing)
        id_db.dump()
        return True


def kw_set(thing):
    if not kw_db.exists(thing):
        kw_db.set(thing, now())
        kw_db.dump()
        return True


def kw_rem(thing):
    if kw_db.exists(thing):
        kw_db.rem(thing)
        kw_db.dump()
        return True


def bno_set(source, title):
    if not bno_db.exists(source):
        bno_db.set(source, title)
        return True


def strip_all_entities(text):
    entity_prefixes = ['@', '#']
    for separator in string.punctuation:
        if separator not in entity_prefixes:
            text = text.replace(separator, ' ')
    words = []
    for word in text.split():
        word = word.strip()
        if word:
            if word[0] not in entity_prefixes:
                words.append(word)
    return ' '.join(words)


def nbo_scraper(first_run=False):
    url = 'https://bnonews.com/index.php/2020/02/the-latest-coronavirus-cases/'
    soup = lovely_soup(url)

    data = []
    new, old = 0, 0

    main = soup.find('div', {'id': 'mvp-content-main'})

    for ul in main.find_all('ul')[1:]:
        start = ul.find_all('li')[0]
        start_time = start.get_text(strip=True)[0:5]
        start_source = start.find('a', href=True)
        if is_time_format(start_time) and start_time and start_source:
            for li in ul.find_all('li'):
                line_text = li.get_text(strip=True).replace(' (Source)', '')
                source = start_source['href']
                title = line_text[7:-1]
                if first_run:
                    new += 1
                    bno_set(source, title)
                else:
                    if bno_set(source, title):
                        reddit.subreddit(target_subreddit).submit(title, url=source)
                        history_dump(title)
                        print('Posted: {}'.format(title))
                        new += 1
                    else:
                        old += 1
    if new:
        bno_db.dump()
    print(f'old: {old} new: {new}')

def lovely_soup(u):
    r = get(u, headers={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1'})
    return BeautifulSoup(r.text, 'lxml')


time_re = re.compile(r'^(([01]\d|2[0-3]):([0-5]\d)|24:00)$')


def is_time_format(s):
    return bool(time_re.match(s))


class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        if from_creator(status) and not status.retweeted and 'RT @' not in status.text:
            user = status.user.name
            body = status.text
            url = False
            keywords = get_keywords()
            yup = [body.lower()
                   for keyword in keywords if keyword in body.lower()]
            if len(yup):
                if len(status.entities['urls']):
                    expanded_url = status.entities['urls'][0]['expanded_url']
                #title = strip_all_entities(body)
                urls = re.findall(r'(https?://\S+)', body)
                if len(urls):
                    for url in urls:
                        body = body.replace(url, '')
                history_dump(body)
                if url:
                    reddit.subreddit(target_subreddit).submit(body, url=expanded_url)
                else:
                    reddit.subreddit(target_subreddit).submit(body, selftext='')
                print('Posted {} tweet to Reddit'.format(user))

    def on_error(self, status_code):
        if status_code == 420:
            return False


myStreamListener = MyStreamListener()
myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)


def from_creator(status):
    if hasattr(status, 'retweeted_status'):
        return False
    elif status.in_reply_to_status_id != None:
        return False
    elif status.in_reply_to_screen_name != None:
        return False
    elif status.in_reply_to_user_id != None:
        return False
    else:
        return True


def error(update, context):
    logger.warning('{}\n{}'.format(update, context.error))
    msg = context.error
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def user_add(update, context):
    for user in context.args:
        if id_set(user):
            msg = 'user {} added'.format(user)
        else:
            msg = 'user {} exists'.format(user)
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        print(msg.strip())


def user_remove(update, context):
    for user in context.args:
        if id_rem(user):
            msg = 'user {} removed'.format(user)
        else:
            msg = 'user {} not in db'.format(user)
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        print(msg.strip())


def user_list(update, context):
    msg = ''
    for x in id_db.getall():
        msg += '{}\n'.format(x)
    if not len(msg):
        msg = 'user db empty'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg.strip())


def word_add(update, context):
    keyword = ' '.join(context.args)
    if kw_set(keyword):
        msg = 'keyword {} added'.format(keyword)
    else:
        msg = 'keyword {} exists'.format(keyword)
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def word_remove(update, context):
    keyword = ' '.join(context.args)
    if kw_rem(keyword):
        msg = 'keyword {} removed'.format(keyword)
    else:
        msg = 'keyword {} not in db'.format(keyword)
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def word_list(update, context):
    msg = ''
    for x in kw_db.getall():
        msg += '{}\n'.format(x)
    if not len(msg):
        msg = 'keyword db empty'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg.strip())


def history(update, context):
    msg = ''
    c = 0
    for x in h_db.getall():
        posted = get_date(h_db.get(x))
        msg += '{}\n{}\n\n'.format(posted, x)
        c += 1
        if c >= 10:
            break
    if not len(msg):
        msg = 'history db empty'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg.strip())


def start_stream(update, context):
    follow_ids = []
    for x in id_db.getall():
        follow_ids.append(x)
    keywords = []
    for x in kw_db.getall():
        keywords.append(x)
    myStream.filter(follow=follow_ids, is_async=True)
    msg = 'Started Twitter stream'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def stop_stream(update, context):
    myStream.disconnect()
    msg = 'Stopped Twitter stream'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


stop_nbo = False

def nbo():
    if len(bno_db.getall()):
        nbo_scraper()
    else:
        nbo_scraper(True)

    c = 0
    while True:
        c += 1
        if c % 15 == 0:
            nbo_scraper()
        time.sleep(randint(1,2))
        global stop_nbo
        if stop_nbo:
            print('Stopped NBO scraper')
            break


def start_nbo_scaper(update, context):
    global stop_nbo
    stop_nbo = False
    nbo_thread = threading.Thread(target=nbo)
    nbo_thread.start()

    msg = 'Started NBO scraper'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def stop_nbo_scaper(update, context):
    global stop_nbo
    stop_nbo = True
    msg = 'Stopping NBO scraper'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    print(msg)


def help(update, context):
    msg = """
/ua - add user id
/ur - remove user id
/ul - lists all user id
/wa - add word
/wr - remove word
/wl - lists all words
/h - post history
/go - start twitter stream
/stop - stop twitter stream
/gonbo - start nbo scraper
/stopnbo - stop nbo scraper
    """
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def main():
    updater = Updater(telegram_api_key, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler(
        'ua', user_add, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'ur', user_remove, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'ul', user_list, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'wa', word_add, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'wr', word_remove, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'wl', word_list, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'h', history, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'go', start_stream, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'stop', stop_stream, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'gonbo', start_nbo_scaper, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'stopnbo', stop_nbo_scaper, Filters.user(username=telegram_admin)))
    dp.add_handler(CommandHandler(
        'help', help, Filters.user(username=telegram_admin)))

    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
