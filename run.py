import praw
import tweepy
import configparser
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import re
import string
import pickledb
import time

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


class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        if from_creator(status) and not status.retweeted and 'RT @' not in status.text:
            user = status.user.name
            title = status.text
            keywords = get_keywords()
            yup = [title.lower()
                   for keyword in keywords if keyword in title.lower()]
            if len(yup):
                urls = re.findall(r'(https?://\S+)', title)
                if len(urls):
                    for url in urls:
                        title = title.replace(url, '')
                #title = strip_all_entities(body)
                history_dump(title)
                if len(urls):
                    reddit.subreddit(target_subreddit).submit(title, url=urls[-1])
                else:
                    reddit.subreddit(target_subreddit).submit(title, selftext='')
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
        'help', help, Filters.user(username=telegram_admin)))

    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
