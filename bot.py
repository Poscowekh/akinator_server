from logging import Logger, getLogger, basicConfig as logger_basic_config, INFO as logINFO
from telegram.update import Update
from telegram.message import Message
from telegram.ext import Updater, CommandHandler, MessageHandler, PollAnswerHandler, Filters, CallbackContext
from Stats import StatsManager
from Akinator import AkinatorState
from BotAkinator import BotAkinator
from bot_db import BotDB
from enum import Enum
from VersionClass import Version
from ConnectionClass import Connection
from file_skeleton import Layouts
from theme_db import ThemeDB
from updates import apply_update, latest_version
from sqlite3 import PARSE_DECLTYPES, PARSE_COLNAMES, IntegrityError


class PossibleActions(Enum):
    # preAkinator states
    start = "start"
    ask_theme = "ask_theme" # == /akinate

    # Akinator states
    ask_question = "ask_question"
    guess = "guess"
    # last_guess = "last_guess" ?
    give_up = "give_up"
    victory = "victory"

    # Update DB states after game
    ask_update = "ask_update"
    ask_update_theme = "ask_update_theme"
    ask_entity_name = "ask_entity_name"
    ask_if_entity_matches = "ask_if_entity_matches"
    ask_entity_description = "ask_entity_description"
    ask_new_question = "ask_question"
    ask_if_question_matches = "ask_if_question_matches"
    ask_answer = "ask_answer"
    ask_continue_update = "ask_continue_update"

    # Update DB
    suggest_update = "suggest_update"
    suggest_theme = "suggest_theme"


def akinator_state_to_possible_action(akinator_state: AkinatorState) -> PossibleActions:
    if akinator_state == AkinatorState.AskQuestion:
        return PossibleActions.ask_question

    elif akinator_state == AkinatorState.MakeGuess:
        return PossibleActions.guess

    # LATER rework when last_guess is introduced as action
    elif akinator_state == AkinatorState.MakeLastGuess:
        return PossibleActions.guess

    elif akinator_state == AkinatorState.GiveUp:
        return PossibleActions.give_up

    elif akinator_state == AkinatorState.Victory:
        return PossibleActions.victory

    else:
        raise RuntimeError()


def answer_value_from_string(string: str) -> float:
    if string == "Yes":
        return 1.0
    elif string == "Probably Yes":
        return 0.5
    elif string == "I do not know":
        return 0.0
    elif string == "Probably No":
        return -0.5
    elif string == "No":
        return -1.0
    else:
        raise ValueError(f"cannot get answer value from {string}")


def available_themes() -> list:
    theme_db = ThemeDB()
    themes = [theme[0] for theme in theme_db.themes()]
    theme_db.close()

    return themes


class BotCommandHandler():
    @staticmethod
    def akinate(update: Update, context: CallbackContext, chosen_theme: str = None):
        themes = available_themes()
        db = BotDB()
        chat_id = Bot.id_from_update(update, context)

        if chosen_theme is not None:
            if chosen_theme not in themes:
                themes = ",".join(themes)
                update.message.reply_text("This is not one of available themes, try again. "
                                          f"Available themes are:\n{themes}")
                db.update_last_session_and_last_action(chat_id, PossibleActions.ask_theme.value)
            else:
                db.clear_game_session(chat_id, PossibleActions.ask_question.value)
                db.set_theme(chat_id, PossibleActions.ask_theme.value, chosen_theme)
                update.message.reply_text(f"You have chosen {chosen_theme}")
                BotPollAnswerHandler.akinator_loop(update, context, chosen_theme)

        else:
            if not themes: # dev only situation
                db.update_last_session_and_last_action(chat_id, PossibleActions.start.value)
                update.message.reply_text("WARNING: No themes available. Please, try again later")
            else:
                themes = ",\n".join(themes)
                db.update_last_session_and_last_action(chat_id, PossibleActions.ask_theme.value)
                update.message.reply_text(f"Choose a theme for the game.\nAvailable themes:\n{themes}\n"
                                          "Type the theme you choose")

        db.close()

    @staticmethod
    def start(update: Update, context: CallbackContext):
        update.message.reply_text('Welcome to SimpleAkinatorBot!\nUse /help for more info')
        db = BotDB()
        try:
            db.add_user(Bot.id_from_update(update, context), PossibleActions.start.value)
        except IntegrityError:  # the user already exists
            db.clear_whole_session(Bot.id_from_update(update, context), PossibleActions.start.value)
        db.close()

    @staticmethod
    def stop(update: Update, context: CallbackContext):
        db = BotDB()
        db.clear_whole_session(Bot.id_from_update(update, context), PossibleActions.start.value)
        db.close()

    @staticmethod
    def back(update: Update, context: CallbackContext):
        db = BotDB()
        chat_id = Bot.id_from_update(update, context)
        last_action = db.get_last_action(chat_id)

        if last_action == PossibleActions.ask_question.value:
            db.remove_last_given_answer(chat_id)
            BotPollAnswerHandler.akinator_loop(update, context)

        elif last_action == PossibleActions.guess.value:
            db.remove_last_wrong_guess(chat_id)
            BotPollAnswerHandler.akinator_loop(update, context)

        #elif last_action == PossibleActions.last_guess.value:
        #    pass

        elif last_action == PossibleActions.give_up.value or last_action == PossibleActions.victory.value:
            pass # LATER

        elif last_action == PossibleActions.ask_update.value:
            # ADD update known values by self
            db.clear_whole_session(chat_id, PossibleActions.ask_theme.value)
            db.update_last_session_and_last_action(chat_id, PossibleActions.ask_theme.value)

        elif last_action == PossibleActions.ask_if_entity_matches.value:
            db.update_last_session_and_last_action(chat_id, PossibleActions.ask_entity_name.value)

        elif last_action == PossibleActions.ask_entity_description.value:
            db.update_last_session_and_last_action(chat_id, PossibleActions.ask_entity_name.value)

        elif last_action == PossibleActions.ask_new_question:
            db.remove_last_new_question(chat_id)

            if db.get_last_tmp_question_id(chat_id) == 0: # back to entity
                db.update_last_session_and_last_action(chat_id, PossibleActions.ask_entity_description)
            else: # previous question
                db.update_last_session_and_last_action(chat_id, PossibleActions.ask_new_question)

        elif last_action == PossibleActions.ask_if_question_matches.value:
            db.remove_last_new_question(chat_id)
            db.update_last_session_and_last_action(chat_id, PossibleActions.ask_new_question.value)

        elif last_action == PossibleActions.ask_answer.value:
            db.remove_last_new_answer(chat_id)
            db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_question_matches.value)

        else: # back to start
            db.clear_whole_session(chat_id, PossibleActions.start.value)
            update.message.reply_text("No step to go back to")

        db.close()

    @staticmethod
    def help(update: Update, context: CallbackContext):
        update.message.reply_text("""
This bot can guess an entity you are thinking of (of course if it is aware of it).
Use /akinate to start the game, choose a theme and proceed with an entity related to this theme
Use /commands to get the list of commands.
""")

    @staticmethod
    def commands(update: Update, context: CallbackContext):
        update.message.reply_text("""
Supported commands:
\t/start to restart bot and erase all info about self from the data baes
\t/help gives brief bot info
\t/commands provides full list of commands
\t/akinate starts the game
\t/update to start creating an update for the last theme you played with
\t/stop to stop the bot
\t/back to go one and only one action back (useful if you answered previous question wrong)
""")

    @staticmethod
    def update(update: Update, context: CallbackContext, theme_: str = None):
        from datetime import datetime, timedelta

        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB(detect_types=PARSE_DECLTYPES | PARSE_COLNAMES)
        session_date = bot_db.get_session_date(chat_id)
        bot_db.change_state(chat_id, PossibleActions.ask_update.value, 0, 4)

        if session_date - datetime.now() >= timedelta(days=1):
            # last session was long enough ago
            BotUserAnswerHandler.ask_update_theme(update, context)

        elif theme_ is None:
            theme = bot_db.get_theme(chat_id)

            if theme is None: # the game was not played and theme was not chosen
                BotUserAnswerHandler.ask_update_theme(update, context)
            else:
                user_id = update.effective_user.id or 0
                question = f"Do you want to update \"{theme}\"?"
                answers = ["Yes", "No"]
                poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
                context.bot_data.update(Layouts.BotData.payload(poll_message, question, answers, chat_id, user_id))
                bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_update_theme.value)

        elif theme_ is not None:
            if theme_ not in available_themes():
                context.bot.send_message(chat_id,
                                         "Attention! This is a new theme and it will not have any entities in it. "
                                         "It will only have the data you insert")
            context.bot.send_message(chat_id, "Great! Please, write the entity's name or surname (if it has one) or "
                                              "a nickname associated with it")
            bot_db.add_update(Bot.id_from_update(update, context), PossibleActions.ask_entity_name.value)
            bot_db.set_latest_update_theme(chat_id, theme_)
            bot_db.set_update_theme(chat_id, theme_)
            bot_db.close()


class BotUserAnswerHandler():
    @staticmethod
    def ask_update_theme(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        context.bot.send_message(chat_id, "Please, specify the theme you want to update")
        bot_db = BotDB()
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_update_theme.value)
        bot_db.close()

    @staticmethod
    def ask_update(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        context.bot.send_message(chat_id, "Could you, please, help the bot update its information data base? "
                                          "The answers you made will be used to adjust the existing data base"
                                          "\nUse /update to start the update"
                                          "\nUse /akinate to play again")
        bot_db = BotDB()
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_update.value)
        bot_db.close()

    @staticmethod
    def entity_name(update: Update, context: CallbackContext, name: str):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        matches_list = list()

        theme = bot_db.get_theme(chat_id)
        latest_theme_version = latest_version(theme)
        if latest_theme_version != Version(0, 0, 0):
            db = Connection(Connection.Type.server, theme, latest_theme_version)
            matches_list = db.search_name(name)
            db.close()

        bot_db.add_entity(chat_id, PossibleActions.ask_entity_name.value)
        bot_db.add_entity_name(chat_id, PossibleActions.ask_entity_name.value, name)

        if not matches_list:
            #update.message.reply_text("This seems to be a completely new entity. Please, describe it briefly")
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_entity_description.value)
            BotUserAnswerHandler.ask_entity_desc(update, context)
        elif len(matches_list) == 1:
            name = matches_list[0][0]
            question = f"Let's first check whether this entity already exists. Is your entity {name}?"
            answers = ["Yes", "No"]
            poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
            context.bot_data.update(Layouts.BotData.payload(poll_message, question, answers, chat_id, name))
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_entity_matches.value)
        else:
            matches_list = [str(match[0]) for match in matches_list]
            names = ",\n".join(matches_list)
            update.message.reply_text("Let's first check whether this entity already exists. "
                                      f"If one of this entities is the same as yours, please, write it's name: {names}"
                                      "\nIf your entity is not listed then rewrite its name")
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_entity_matches.value)

        bot_db.close()

    @staticmethod
    def entity_matches(update: Update, context: CallbackContext, name: str = None):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        if name is not None:
            bot_db.add_entity_name(chat_id, PossibleActions.ask_if_entity_matches.value, name)
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_entity_matches.value)
            # no check if name was on the list lol
            #BotUserAnswerHandler.
            bot_db.close()
            context.bot.send_message(chat_id, "Now, please, add some more questions related to this entity if you can.")
            BotUserAnswerHandler.ask_new_question(update, context)
        else:
            BotUserAnswerHandler.ask_entity_desc(update, context)

    @staticmethod
    def ask_entity_desc(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        context.bot.send_message(chat_id, "This entity is new.\nPlease, describe it briefly")
        bot_db = BotDB()
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_entity_description.value)
        bot_db.close()

    @staticmethod
    def entity_desc(update: Update, context: CallbackContext, desc: str):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        bot_db.add_entity_desc(chat_id, PossibleActions.ask_entity_description.value, desc)
        given_answers = bot_db.get_given_answers(chat_id, ["question_id", "answer_value"])
        for id, value in given_answers:
            if value == 0.0:
                continue
            bot_db.add_answer(chat_id)
            bot_db.add_answer_existing_once(chat_id, id, value)
        bot_db.close()
        BotUserAnswerHandler.ask_new_question(update, context)

    @staticmethod
    def ask_new_question(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        context.bot.send_message(chat_id, "Please type new question's text or \"NO\" to stop")
        bot_db = BotDB()
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_new_question.value)
        bot_db.close()

    @staticmethod
    def question_text(update: Update, context: CallbackContext, text: str):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        theme = bot_db.get_theme(chat_id)
        latest_theme_version = latest_version(theme)
        db = Connection(Connection.Type.server, theme, latest_theme_version)
        matches_list = db.search_text(text)
        db.close()

        bot_db.add_question(chat_id, PossibleActions.ask_new_question.value)
        bot_db.add_question_text(chat_id, text)

        if not matches_list:
            #update.message.reply_text("This seems to be a completely new question")
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_question_matches.value)
            BotUserAnswerHandler.question_matches(update, context, text)
        elif len(matches_list) == 1:
            text = matches_list[0][0]
            question = f"Let's first check whether this question already exists. Is your question \"{text}\"?"
            answers = ["Yes", "No"]
            poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
            context.bot_data.update(Layouts.BotData.payload(poll_message, question, answers, chat_id, text))
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_question_matches.value)
        else:
            matches_list = [str(match[0]) for match in matches_list]
            texts = "\n".join(matches_list)
            update.message.reply_text("Let's first check whether this question already exists. "
                                      f"If one of this questions is the same as yours, please, copy it's text:\n{texts}"
                                      f"If your question is not in the list just retype it")
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_question_matches.value)

        bot_db.close()

    @staticmethod
    def question_matches(update: Update, context: CallbackContext, text: str = None):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()

        if text is not None:
            context.bot.send_message(chat_id, "This is a new question")
            bot_db.add_question_text(chat_id, text)
            bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_if_entity_matches.value)
            bot_db.close()
            #context.bot.send_message(chat_id, "Now, please, add some more questions related to this entity if you can.")
            BotUserAnswerHandler.ask_answer(update, context)
        else:
            BotUserAnswerHandler.ask_answer(update, context)

    @staticmethod
    def ask_answer(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        user_id = update.effective_user.id or 0
        bot_db = BotDB()
        question = f"How does your entity answer this question?"
        answers = ["Yes", "No"]
        poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
        context.bot_data.update(Layouts.BotData.payload(poll_message, question, answers, chat_id, user_id))
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_answer.value)
        bot_db.close()

    @staticmethod
    def new_answer(update: Update, context: CallbackContext, answer_value):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        bot_db.add_answer(chat_id)
        bot_db.add_answer_value(chat_id, answer_value)
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_continue_update.value)
        bot_db.close()
        BotUserAnswerHandler.ask_new_question(update, context)

    @staticmethod
    def continue_update(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        context.bot.send_message(chat_id, "Would you like to add another entity?\n"
                                          "Enter it's name or \"NO\" to save the update")
        bot_db = BotDB()
        bot_db.update_last_session_and_last_action(chat_id, PossibleActions.ask_continue_update.value)
        bot_db.close()

    @staticmethod
    def update_done(update: Update, context: CallbackContext):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        bot_db.complete_update(chat_id, PossibleActions.start.value)
        if bot_db.update_complete_count() >= 1: ## WARNING
            apply_update(bot_db.get_user_updates())
        bot_db.close()
        context.bot.send_message(chat_id, "Thank you for the update. It will soon be inserted into the data base")


class BotMessageHandler():
    @staticmethod
    def parse_message(update: Update, context: CallbackContext):
        message = update.message.text

        if message[0] == '/':
            update.message.reply_text("This command is not supported. Use /commands to see the list of all commands")
            return

        chat_id = Bot.id_from_update(update, context)
        db = BotDB()
        last_action = db.get_last_action(chat_id)
        db.close()

        if last_action == PossibleActions.ask_theme.value:
            BotCommandHandler.akinate(update, context, message)

        elif last_action == PossibleActions.ask_entity_name.value:
            BotUserAnswerHandler.entity_name(update, context, message)

        elif last_action == PossibleActions.ask_if_entity_matches.value:
            if message.capitalize() == "No":
                BotUserAnswerHandler.ask_entity_desc(update, context)
            else:
                BotUserAnswerHandler.entity_matches(update, context, message)

        elif last_action == PossibleActions.ask_entity_description.value:
            BotUserAnswerHandler.entity_desc(update, context, message)

        elif last_action == PossibleActions.ask_if_question_matches.value:
            if message.capitalize() == "No":
                BotUserAnswerHandler.ask_answer(update, context)
            else:
                BotUserAnswerHandler.question_text(update, context, message)

        elif last_action == PossibleActions.ask_new_question.value:
            if message.capitalize() == "No":
                BotUserAnswerHandler.continue_update(update, context)
            else:
                BotUserAnswerHandler.question_text(update, context, message)

        elif last_action == PossibleActions.ask_continue_update.value:
            if message.capitalize() == "No":
                BotUserAnswerHandler.update_done(update, context)
            else:
                BotUserAnswerHandler.entity_name(update, context, message)

        elif last_action == PossibleActions.ask_update_theme.value:
            db = BotDB()
            db.set_theme(chat_id, PossibleActions.ask_update.value, message)
            db.close()
            BotCommandHandler.update(update, context, message)

        else: # ignoring any message from user when they are not expected
            pass


class BotPollAnswerHandler():
    @staticmethod
    def akinator_loop(update: Update, context: CallbackContext, theme: str = None, user_id = None):
        chat_id = Bot.id_from_update(update, context)
        bot_db = BotDB()
        theme_ = theme if theme is not None else bot_db.get_theme(chat_id)
        akinator = BotAkinator(theme_, latest_version(theme_), chat_id)
        state = akinator.state
        poll_message: Message
        payload: dict = {}

        if state == AkinatorState.AskQuestion:
            id, text = akinator.ask_question()
            answers = ["Yes", "Probably Yes", "I do not know", "Probably No", "No"]
            poll_message = context.bot.send_poll(chat_id, text, answers, is_anonymous=False)
            payload = Layouts.BotData.payload(poll_message, text, answers, chat_id, user_id)
            bot_db.save_akinator_loop(chat_id, akinator_state_to_possible_action(state).value,
                                      akinator.iteration, state, id)

        elif state == AkinatorState.MakeGuess:
            id, name = akinator.guess()
            answers = ["Yes", "No"]
            question = f"Is your entity {name}?"
            poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
            payload = Layouts.BotData.payload(poll_message, question, answers, chat_id, user_id)
            bot_db.save_akinator_loop(chat_id, akinator_state_to_possible_action(state).value,
                                      akinator.iteration, state, id)

        elif state == AkinatorState.MakeLastGuess:
            id, name = akinator.last_guess()
            answers = ["Yes", "No"]
            question = f"Is your entity {name}?"
            poll_message = context.bot.send_poll(chat_id, question, answers, is_anonymous=False)
            payload = Layouts.BotData.payload(poll_message, question, answers, chat_id, user_id)
            bot_db.save_akinator_loop(chat_id, akinator_state_to_possible_action(state).value,
                                      akinator.iteration, state, id)

        elif state == AkinatorState.Victory:
            context.bot.send_message(chat_id, "Thank you for the great game!\nTo play again use /akinate")
            bot_db.update_last_session_and_last_action(chat_id, akinator_state_to_possible_action(state).value)

        elif state == AkinatorState.GiveUp:
            context.bot.send_message(chat_id, "Akinator is clueless what entity you have thought of")
            bot_db.update_last_session_and_last_action(chat_id, akinator_state_to_possible_action(state).value)
            BotUserAnswerHandler.ask_update(update, context)


        # Save some info about the poll in the bot_data for later use in poll_answer
        context.bot_data.update(payload)
        bot_db.close()

    @staticmethod
    def poll_answer(update: Update, context: CallbackContext):
        answer = update.poll_answer
        poll_id = answer.poll_id
        user_id = update.effective_user.id

        """if context.bot_data[poll_id]["user_id"] is None:
            context.bot_data[poll_id]["user_id"] = user_id
        elif user_id != context.bot_data[poll_id]["user_id"]:
            Bot.logger.warning("user ids: '%s' '%s'", user_id, context.bot_data[poll_id]["user_id"])
            # not the user playing the game. may be send response that they should start their own bot
            return"""
        answers = context.bot_data[poll_id]["answers"]
        chat_id = context.bot_data[poll_id]["chat_id"]

        selected_option = -1
        if not answer.option_ids:  # vote retracted
            BotCommandHandler.back(update, context)
            # restart the poll (put to /back later)
            update.poll.is_closed = False
            context.bot.send_message(chat_id, "Voice retracted, resending the poll")
            context.bot.send_poll(chat_id,
                                  context.bot_data[poll_id]["question"],
                                  context.bot_data[poll_id]["answers"],
                                  context.bot_data[poll_id]["message_id"],
                                  is_anonymous=False)
            return
        else:
            selected_option = answer.option_ids[0]
            answer_string = answers[selected_option]  # only one answer possible

        #context.bot_data[poll_id]["answer_count"] += 1
        #if context.bot_data[poll_id]["answer_count"] == 1:
        # Close poll after user voted
        context.bot.stop_poll(chat_id, context.bot_data[poll_id]["message_id"])

        bot_db = BotDB()
        theme = bot_db.get_theme(Bot.id_from_update(update, context))
        iteration, state = bot_db.get_iteration_and_state(chat_id)
        answer_value = answer_value_from_string(answers[selected_option])

        if state == AkinatorState.AskQuestion.value:
            bot_db.add_given_answer(chat_id, answer_value)

        elif state == AkinatorState.MakeGuess.value:
            if answer_value == 1.0:
                bot_db.victory(chat_id)
                bot_db.close()
                return
            else:
                bot_db.add_wrong_guess(chat_id)

        elif state == AkinatorState.MakeLastGuess.value:  # same as MakeGuess for bot?
            if answer_value == 1.0:
                bot_db.victory(chat_id)
                bot_db.close()
                return
            else:
                bot_db.add_wrong_guess(chat_id)

        elif state == AkinatorState.Victory.value or state == AkinatorState.GiveUp.value:
            # either game was finished successfully or just /update was called
            latest_action = bot_db.get_last_action(chat_id)

            if latest_action == PossibleActions.ask_if_entity_matches.value:
                if answer_value == 1.0:
                    BotUserAnswerHandler.entity_matches(update, context, context.bot_data[poll_id]["additional_info"])
                else:
                    BotUserAnswerHandler.entity_matches(update, context)

            elif latest_action == PossibleActions.ask_if_question_matches.value:
                if answer_value == 1.0:
                    BotUserAnswerHandler.question_matches(update, context, context.bot_data[poll_id]["additional_info"])
                else:
                    BotUserAnswerHandler.question_matches(update, context)
                bot_db.close()
                return

            elif latest_action == PossibleActions.ask_answer.value:
                BotUserAnswerHandler.new_answer(update, context, answer_value)

            elif latest_action == PossibleActions.ask_update.value:
                if answer_value == 1.0:
                    BotUserAnswerHandler.ask_update_theme(update, context)
                else:
                    BotCommandHandler.stop(update, context)
                    bot_db.update_last_session_and_last_action(chat_id, PossibleActions.start.value)

            elif latest_action == PossibleActions.ask_update_theme.value:
                if answer_value == 1.0:
                    BotCommandHandler.update(update, context, bot_db.get_theme(chat_id))
                else:
                    context.bot.send_message(chat_id, "Please, type the theme you want to update")
                    bot_db.close()
                    return

            # not to call the akinator loop
            bot_db.close()
            return

        else:
            raise RuntimeError("Received unexpected poll answer")

        bot_db.close()
        BotPollAnswerHandler.akinator_loop(update, context, theme, user_id)


class Bot(Updater):
    # safe as bot is unique
    #__db__: BotDB = BotDB() # just to create tables and init the database if needed
    HTTP_API: str = "1985794839:AAF3ltG9T_pv7aJzlFvPhzmP6n8-9aLrAq0"
    global_stats: StatsManager = StatsManager(StatsManager.Type.global_server)
    possible_actions: list = [action.value for action in PossibleActions]

    @staticmethod
    def id_from_update(update: Update, context: CallbackContext) -> int:
        if update.effective_chat:
            # regular message
            return update.effective_chat.id
        else:
            # poll answer
            return context.bot_data[update.poll_answer.poll_id]["chat_id"]

    def __init__(self, use_context: bool = True):
        Updater.__init__(self, Bot.HTTP_API, use_context=use_context)

        self.logger = Logger(__name__)

        self.__init_logger__()
        self.__init_error_handler__()

        self.__init_command_handlers__()
        self.__init_poll_answer_handlers__()
        self.__init_message_handlers__()

        # not used further
        #Bot.__db__.execute("DROP TABLE users")
        #Bot.__db__.execute("DROP TABLE wrong_entities")
        #db = BotDB()
        #db.close()

    def __init_logger__(self):
        logger_basic_config(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logINFO)
        Bot.logger = getLogger(__name__)
        self.logger = getLogger(__name__)

    def __error__(self, update: Update, context: CallbackContext):
        self.logger.warning('Update "%s" caused error "%s"', update.update_id, context.error.with_traceback())

    def __init_error_handler__(self):
        self.dispatcher.add_error_handler(self.__error__)

    def __init_command_handlers__(self):
        self.dispatcher.add_handler(CommandHandler("start", BotCommandHandler.start))
        self.dispatcher.add_handler(CommandHandler("help", BotCommandHandler.help))
        self.dispatcher.add_handler(CommandHandler("commands", BotCommandHandler.commands))
        self.dispatcher.add_handler(CommandHandler("akinate", BotCommandHandler.akinate)) # gives themes to choose
        self.dispatcher.add_handler(CommandHandler("stop", BotCommandHandler.stop))
        self.dispatcher.add_handler(CommandHandler("back", BotCommandHandler.back))
        self.dispatcher.add_handler(CommandHandler("update", BotCommandHandler.update))

    def __init_poll_answer_handlers__(self):
        self.dispatcher.add_handler(PollAnswerHandler(BotPollAnswerHandler.poll_answer))

    def __init_message_handlers__(self):
        self.dispatcher.add_handler(MessageHandler(Filters.text, BotMessageHandler.parse_message))

    @staticmethod
    def start_game(update: Update, context: CallbackContext):
        update.message.reply_poll("Click 'START' whenever you are ready", ["START"])

    def main(self):
        self.start_polling()
        self.idle()


# for testing
if __name__ == "__main__":
    # init theme DB
    #theme_db = ThemeDB()
    #theme_db.drop()
    #theme_db.create_tables()
    #theme_db.create_new_theme("test", Version(1, 3))
    #print(theme_db.execute("SELECT * FROM themes").fetchall())
    #print(theme_db.execute("SELECT * FROM versions").fetchall())
    #theme_db.close()

    # init game info DB
    #info_db = Connection(Connection.Type.server, "test", Version(1, 3))
    #info_db.close()

    # clear user data
    bot_db = BotDB()
    #bot_db.drop()
    #bot_db.create_tables()
    bot_db.close()

    bot = Bot()
    bot.main()

