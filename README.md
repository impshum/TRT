## TRT

Streams Twitter and reposts to a chosen subreddit when keywords are found in users tweets. Controllable via Telegram.

### Instructions

-   Install requirements `pip install -r requirements.txt`
-   Create Reddit (script) app at <https://www.reddit.com/prefs/apps/> and get keys
-   Create Twitter app at <https://apps.twitter.com/> and get keys
-   Create Telegram bot with @BotFather on Telegram and get keys
-   Edit conf.ini with your details
-   Run it `python run.py`

### Bot commands

-   `/ua` - add user id  
-   `/ur` - remove user id  
-   `/ul` - lists all user id  
-   `/wa` - add word  
-   `/wr` - remove word  
-   `/wl` - lists all words  
-   `/h` - post history
-   `/start` - start twitter stream
-   `/stop` - stop twitter stream  

### Notes

-   Add user ids and keywords when the stream is stopped. To update you have to stop the stream, add then start again.
-   I will not be held responsible for any bad things that might happen to you or your accounts whilst using this bot. Stay safe.
