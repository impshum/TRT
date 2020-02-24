import praw
import tweepy
import configparser
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters


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

reddit = praw.Reddit(
    username=reddit_user,
    password=reddit_pass,
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent='RedTwit (by u/impshum)'
)

auth = tweepy.OAuthHandler(twitter_consumer_key, twitter_consumer_secret)
auth.set_access_token(twitter_access_token, twitter_access_token_secret)
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


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


class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        with open('keywords.txt') as f:
            keywords = f.read().splitlines()

        if from_creator(status) and not status.retweeted and 'RT @' not in status.text:
            user = status.user.name
            body = status.text
            yup = [body.lower() for keyword in keywords if keyword in body.lower()]
            if len(yup):
                reddit.subreddit(target_subreddit).submit(body, selftext='')
                print(f'Posted {user} tweet to Reddit')

    def on_error(self, status_code):
        if status_code == 420:
            return False


myStreamListener = MyStreamListener()
myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)


def error(update, context):
    logger.warning(f'Update {update} caused error {context.error}')
    context.bot.send_message(chat_id=update.effective_chat.id, text=context.error)


def remove_line(file, target):
    with open(file) as f:
        data = f.read().splitlines()

    all = []

    for line in data:
        if target not in line:
            all.append(line)

    with open(file, 'w') as f:
        f.write('\n'.join(all))


def do_input(update, context):
    user_input = update.message.text
    start = '/start'
    stop = '/stop'
    add_u = '/ua '
    remove_u = '/ur '
    list_u = '/ul'
    add_w = '/wa '
    remove_w = '/wr '
    list_w = '/wl'

    if user_input == start:
        msg = 'Starting Twitter stream'
        with open('follow_ids.txt') as f:
            follow_ids = f.read().splitlines()
        myStream.filter(follow=follow_ids, async=True)
        print('Starting Twitter stream')
    elif user_input == stop:
        msg = 'Stopping Twitter stream'
        print('Stopping twitter stream')
        myStream.disconnect()

    elif user_input.startswith(add_u):
        user_input = user_input.replace(add_u, '')
        if len(user_input):
            with open('follow_ids.txt', 'a') as f:
                f.write(f'{user_input}\n')
            msg = f'Added {user_input}'
    elif user_input.startswith(remove_u):
        user_input = user_input.replace(remove_u, '')
        if len(user_input):
            remove_line('follow_ids.txt', user_input)
            msg = f'Removed {user_input}'

    elif user_input.startswith(add_w):
        user_input = user_input.replace(add_w, '')
        if len(user_input):
            with open('keywords.txt', 'a') as f:
                f.write(f'{user_input}\n')
            msg = f'Added {user_input}'
    elif user_input.startswith(remove_w):
        user_input = user_input.replace(remove_w, '')
        if len(user_input):
            remove_line('keywords.txt', user_input)
            msg = f'Removed {user_input}'

    elif user_input == list_u:
        with open('follow_ids.txt') as f:
            msg = f.read()

    elif user_input == list_w:
        with open('keywords.txt') as f:
            msg = f.read()

    else:
        msg = 'You missed something!'

    update.message.reply_text(msg)


def main():
    updater = Updater(telegram_api_key, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text, do_input))
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
