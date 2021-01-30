import logging
import re
import configparser

from threading import Timer
from plexapi.server import PlexServer
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (Updater, CommandHandler, CallbackQueryHandler, ConversationHandler,
                          MessageHandler, Filters)


CONFIG = configparser.ConfigParser()
CONFIG.read("poll.ini")

logging.basicConfig(format='%(asctime)s %(lineno)d - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

SELECT = range(1)

PLEX = PlexServer(CONFIG['Plex']['baseURL'], CONFIG['Plex']['token'])


class StopAnswer(Exception):

    def __init__(self, message):
        super().__init__()
        self.message = message


class Poll:

    def __init__(self, bot, args):
        self.bot = bot
        self.args = args

    def post_answer(self, query):
        pass

    def handle_update(self, update):
        query = update.callback_query
        try:
            getattr(self, query.data)(update)
            self.post_answer(query)
        except StopAnswer as stop_answer:
            self.bot.answer_callback_query(query.id, text=stop_answer.message)


class RemovePoll(Poll):

    def __init__(self, bot, args, chat_id, timeout):
        super().__init__(bot, args)
        self.message_id = None
        self.chat_id = chat_id
        self.timeout = timeout
        self.timer = Timer(60 * 60 * timeout, self.remove_media)
        self.media = self._media()

    def create_link(self):
        imdb_url = "https://www.imdb.com/title/"

        if "imdb://" in self.media.guid:
            return imdb_url + self.media.guid.split('//')[1]
        if "thetvdb://" in self.media.guid:
            return "https://thetvdb.com/?tab=series&id=" + self.media.guid.split('//')[1]

        for guid in self.media.guids:
            if "imdb://" in guid.id:
                return imdb_url + guid.id.split('//')[1]
            if "tmdb://" in guid.id:
                return "https://www.themoviedb.org/movie/" + guid.id.split('//')[1]

        return None

    def create_poll(self):
        buttons = [
            [
                InlineKeyboardButton('Yes', callback_data='answer_yes')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        descr_url = self.create_link()

        text = (f"*{self.media.title} ({self.media.year})* {self.media.type} is scheduled for "
                f"removal within *{self.timeout} hours*. Would you like to keep it? "
                f"{descr_url if descr_url is not None else ''}")

        self.message_id = self.bot.send_message(chat_id=self.chat_id,
                                                text=text, parse_mode='markdown',
                                                reply_markup=reply_markup).message_id
        LOGGER.info("Remove poll started for '%s'", self.media.title)
        self.timer.start()

    def edit_message(self, new_text):
        self.bot.edit_message_text(new_text,
                                   chat_id=self.chat_id,
                                   parse_mode='markdown',
                                   message_id=self.message_id)

    def post_answer(self, query):
        self.edit_message(("*{}* removal is postponed. "
                           "Happy watching :)").format(self.args))

    def _media(self):
        title = re.search(r': (.*) \(', self.args).group(1)
        year = re.search(r'.* \((.*)\)', self.args).group(1)
        media = PLEX.library.search(title, year=year)
        if len(media) > 1:
            LOGGER.error('Cannot remove, more that one media %s %s', title, year)
            raise
        return media[0]

    def remove_media(self):
        if not self.media:
            LOGGER.error('Could not find media %s %s', self.media.title, self.media.year)
        self.media.delete()
        self.edit_message('*{}* was removed'.format(self.args))

    def answer_yes(self, update):
        LOGGER.info("User '%s' wants to keep media '%s'",
                    update.callback_query.from_user.first_name,
                    self.args)
        self.timer.cancel()


POLLS = {}


def question_remove(update, context):
    poll = RemovePoll(context.bot,
                      update.message.text,
                      CONFIG['Telegram']['poll_channel'],
                      CONFIG['General'].getint('poll_timeout_hours'))
    poll.create_poll()
    POLLS[poll.message_id] = poll
    return ConversationHandler.END


def handle_answer(update, context):
    POLLS[update.callback_query.message.message_id].handle_update(update)


def handle_cancel(update, context):
    return ConversationHandler.END


def handle_search(update, context):
    search_string = ' '.join(context.args)
    if not search_string:
        update.message.reply_text("You did not provide a search term")
        return ConversationHandler.END

    LOGGER.info("Started querying PLEX server for '%s'", search_string)
    search_results = PLEX.library.search(search_string)
    filtered = [s for s in search_results if hasattr(s, "year") and s.year is not None]
    if not filtered:
        update.message.reply_text("No media found")
        return ConversationHandler.END

    buttons = [
        [KeyboardButton(f"{media.type}: {media.title} ({media.year})")] for media in filtered
    ]
    update.message.reply_text("Choose media",
                              reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))

    return SELECT


def error_handler(update, context):
    LOGGER.error(context.error)


def main():
    updater = Updater(CONFIG['Telegram']['bot_token'], use_context=True)

    updater.dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler('remove', handle_search, pass_args=True)],
        states={
            SELECT: [MessageHandler(Filters.text, question_remove)]
        },
        fallbacks=[CommandHandler('cancel', handle_cancel)],
        allow_reentry=True
    ))
    updater.dispatcher.add_handler(CallbackQueryHandler(handle_answer))
    updater.dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
