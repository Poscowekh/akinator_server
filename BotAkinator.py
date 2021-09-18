from Akinator import GivenAnswer, AkinatorState, AkinationAlgorithms
from bot_db import BotDB
from VersionClass import Version
from ConnectionClass import Connection


class BotAkinator():
    iteration_limit: int = 24
    start_selective_rating_increase_iteration: int = 7
    start_guess_iteration: int = 5
    guess_limit: int = 7

    guess_threshold_entity_multiplier: float = 0.85
    guess_threshold_question_multiplier: float = 1.05
    guess_threshold_minimum: float = 0.5
    leader_difference: float = 0.5

    def __init__(self, theme: str, version: Version, chat_id: int,
                 connection_type: Connection.Type = Connection.Type.game):
        self.game_db = Connection(connection_type, theme, version)
        bot_db = BotDB()

        self.chat_id = chat_id
        iteration, state = bot_db.get_iteration_and_state(chat_id)

        self.iteration = iteration or 0
        self.state = AkinatorState(state) or AkinatorState.AskQuestion


        # list[tuple[int, float]]
        self.user_answers = bot_db.get_given_answers(chat_id, ["question_id", "answer_value"]) or list()
        self.wrong_entities = bot_db.get_wrong_guesses(chat_id, ["entity_id"]) or list()  # list[tuple[int]]

        bot_db.close()
        if self.user_answers:
            self.game_db.__updatemany__("questions", "id", ["used"],
                                        [(1, id) for id, answer_value in self.user_answers])
        self.guess_count = 0
        if self.wrong_entities:
            self.game_db.__updatemany__("entities", "id", ["rating", "used"],
                                        [(-10000.0, 1, id[0]) for id in self.wrong_entities])
            self.guess_count = len(self.wrong_entities)

        self.stats_recomputed = False
        self.guess_threshold = 0.5
        self.compute_threshold = 0.0

        self.probable_entities = list()  # list[tuple[int, float]
        self.probable_questions = list()  # list[tuple[int]]

        self.next_state()

    def __del__(self):
        self.game_db.close()

    def __recompute_stats(self):
        if not self.user_answers:
            self.stats_recomputed = True
            return

        AkinationAlgorithms.increasemany_rating(self.game_db, self.user_answers)

        maximum, minimum = self.game_db.entity_min_max_rating()

        # same as (max-min)/2+[max-guess_threshold-(max-min)/2]/2
        self.compute_threshold = 0.5 * (1.5 * maximum - 0.5 * minimum - self.guess_threshold)

        #self.compute_threshold = minimum + (maximum - minimum) / 2 # * self.guess_threshold
        #minimum * self.guess_threshold + maximum * abs(1 - self.guess_threshold)
        self.probable_entities = AkinationAlgorithms.best_character(self.game_db, self.compute_threshold).fetchall()
        self.stats_recomputed = True

    def choose_chars(self) -> list:  # list[tuple[int, float]]
        if not self.stats_recomputed:
            self.__recompute_stats()
        return self.probable_entities

    def leader_is_good(self) -> bool:
        if not self.stats_recomputed:
            self.__recompute_stats()

        if len(self.probable_entities) == 1:
            return True
        elif len(self.probable_entities) == 0:
            return False

        leader_rating = self.probable_entities[0][1]
        next_rating = self.probable_entities[1][1]

        return leader_rating - next_rating >= self.compute_threshold * BotAkinator.leader_difference
        #return leader_rating - next_rating >= self.guess_threshold * BotAkinator.leader_difference # * \
               # self.iteration / BotAkinator.iteration_limit

    def guess(self) -> tuple:  # tuple[id, name]
        id = self.probable_entities[0][0]
        name = self.game_db.entity_get_name(id)
        self.guess_count += 1

        return id, name

    def last_guess(self) -> tuple:  # tuple[list[tuple[id, name]], int]
        #ids_and_names = [(entity[0], self.game_db.entity_get_name(entity[0])) for entity in self.probable_entities]
        #return ids_and_names, BotAkinator.guess_limit - self.guess_count
        return self.guess()

    def ask_question(self) -> tuple:  # tuple[id, text]
        id = self.probable_questions[0][0]
        text = self.game_db.question_get_text(id)
        return id, text

    def choose_questions(self) -> list:  # list[tuple[id,]]
        if not self.stats_recomputed:
            self.__recompute_stats()

        self.guess_threshold *= BotAkinator.guess_threshold_question_multiplier ** self.iteration
        self.probable_questions = AkinationAlgorithms.best_question(self.game_db, self.compute_threshold).fetchall()

        return self.probable_questions

    def receive_answer(self, question_id: int, answer: float):
        self.user_answers.append(GivenAnswer(question_id, answer))
        self.__recompute_stats()

    def receive_guess(self, entity_id: int, is_right: bool):
        if not is_right:
            self.wrong_entities.append(entity_id)
            self.__recompute_stats()
        else:
            self.state = AkinatorState.Victory

    def receive_last_guess(self, there_is_right: bool, entity_id: int = None):
        if there_is_right:
            self.state = AkinatorState.Victory
        else:
            self.state = AkinatorState.GiveUp

    # Decides upon next state of game
    def next_state(self):
        if not self.stats_recomputed:
            self.__recompute_stats()

        if self.state == AkinatorState.AskQuestion:
            self.choose_questions()

            if self.iteration > BotAkinator.start_guess_iteration and self.leader_is_good():
                self.state = AkinatorState.MakeGuess
            else:
                if self.iteration >= BotAkinator.iteration_limit or len(self.probable_questions) == 0:
                    self.state = AkinatorState.GiveUp
                else:
                    self.state = AkinatorState.AskQuestion

        elif self.state == AkinatorState.MakeGuess:
            self.choose_questions()

            if len(self.probable_questions) == 0 or self.guess_count >= BotAkinator.guess_limit:
                # no more questions
                if self.guess_count >= BotAkinator.guess_limit:
                    self.state = AkinatorState.GiveUp
                else:
                    self.state = AkinatorState.MakeLastGuess
            else:
                # trying next question
                self.guess_threshold = min(BotAkinator.guess_threshold_entity_multiplier * self.guess_threshold,
                                           BotAkinator.guess_threshold_minimum)
                self.state = AkinatorState.AskQuestion

        elif self.state == AkinatorState.MakeLastGuess:
            self.choose_chars()

            if self.guess_count >= BotAkinator.guess_limit:
                self.state = AkinatorState.GiveUp
            else:
                self.state = AkinatorState.MakeLastGuess

        elif self.state == AkinatorState.Victory:
            # ends the game same as restart or stop ?
            pass

        else:  # self.state == GiveUp, Stop, etc:
            # excuse me ?
            pass

        self.iteration += 1
        self.stats_recomputed = False