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

    def __init__(self, bot, args, chat_id):
        super().__init__(bot, args)
        self.message_id = None
        self.chat_id = chat_id
        self.timer = Timer(60*60*CONFIG['General'].getint('poll_timeout_hours'), self.remove_movie)
        self.movie = self._movie()

    def create_poll(self):
        buttons = [
            [
                InlineKeyboardButton('Yes', callback_data='answer_yes')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        descr_url = None
        imdb_id = re.search('tt.*[0-9]', self.movie.guid)
        themoviedb_id = re.search('themoviedb://([0-9].*)', self.movie.guid)
        if imdb_id:
            descr_url = 'https://www.imdb.com/title/{}'.format(imdb_id.group())
        elif themoviedb_id:
            descr_url = 'https://www.themoviedb.org/tv/{}'.format(themoviedb_id.group(1))

        text = ("*{}* is scheduled for removal within *{} hours*. "
                "Would you like to keep it? "
                "{}").format(self.args, CONFIG['General'].getint('poll_timeout_hours'), descr_url)
        self.message_id = self.bot.send_message(chat_id=self.chat_id,
                                                text=text, parse_mode='markdown',
                                                reply_markup=reply_markup).message_id
        self.timer.start()

    def edit_message(self, new_text):
        self.bot.edit_message_text(new_text,
                                   chat_id=self.chat_id,
                                   parse_mode='markdown',
                                   message_id=self.message_id)

    def post_answer(self, query):
        self.edit_message(("*{}* removal is postponed. "
                           "Happy watching :)").format(self.args))

    def _movie(self):
        title = re.search(r'(.*) \(', self.args).group(1)
        year = re.search(r'.* \((.*)\)', self.args).group(1)
        movie = PLEX.library.search(title, year=year)
        if len(movie) > 1:
            LOGGER.error('Cannot remove, more that one movie %s %s', title, year)
            raise
        return movie[0]

    def remove_movie(self):
        if not self.movie:
            LOGGER.error('Could not find movie %s %s', self.movie.title, self.movie.year)
        self.movie.delete()
        self.edit_message('*{}* was removed'.format(self.args))

    def answer_yes(self, update):
        LOGGER.info("User %s wants to keep movie %s",
                    update.callback_query.from_user.first_name,
                    self.args)
        self.timer.cancel()


POLLS = {}


def question_remove(update, context):
    poll = RemovePoll(context.bot, update.message.text, CONFIG['Telegram']['poll_channel'])
    poll.create_poll()
    POLLS[poll.message_id] = poll
    return ConversationHandler.END


def handle_answer(update, context):
    POLLS[update.callback_query.message.message_id].handle_update(update)


def handle_cancel(update, context):
    return ConversationHandler.END


def handle_search(update, context):
    search_results = PLEX.search(' '.join(context.args))
    if not search_results:
        update.message.reply_text("No movie found")
        return ConversationHandler.END
    buttons = [
        [KeyboardButton('{} ({})'.format(movie.title, movie.year))] for movie in search_results
    ]
    update.message.reply_text("Choose movie",
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
        fallbacks=[CommandHandler('cancel', handle_cancel)]
    ))
    updater.dispatcher.add_handler(CallbackQueryHandler(handle_answer))
    updater.dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
