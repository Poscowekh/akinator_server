from random import SystemRandom
from file_skeleton import Layouts
from sqlite3 import Cursor
from enum import IntEnum
from ConnectionClass import Connection
from VersionClass import Version


# Class for easier update management
class Update():
    def __init__(self):
        self.data = Layouts.Data.Update.Post.template.value

    def add_entity(self, name: str, questions_and_answers: list, new_questions_and_answers: list = None, description: str = None):
        new_entity = Layouts.Object.New.Entity.template.value
        new_entity["name"] = name
        if description is not None:
            new_entity["description"] = description
        new_entity["questions_and_answers"] = questions_and_answers
        if new_questions_and_answers is not None:
            new_entity["new_questions_and_answers"] = new_questions_and_answers
        for question in new_questions_and_answers:
            if question["text"] not in self.data["new_questions"]:
                self.data["new_questions"].append(question["text"])

    # adds question if its analog is not already listed
    def try_add_question(self, text: str):
        if "text" not in self.data["new_questions"]:
            self.data["new_questions"].append(text)

    # no repeat check
    #def add_additional_answer(self, entity_id: int, question_id: int, answer_value: float):
    #    additional_answer = Template.Object.MODIFIED_ANSWER.value
    #    additional_answer["entity_id"] = entity_id
    #    additional_answer["question_id"] = question_id
    #    additional_answer["answer_value"] = answer_value
    #    self.data["additional_answers"].append(additional_answer)


class GivenAnswer():
    def __init__(self, question_id: int, answer_value: float):
        self.question_id = question_id
        self.answer_value = answer_value


class AkinationAlgorithms():
    good_answer_weight: float = 1.1
    bad_answer_weight: float = 0.8
    no_answer_constant: float = -0.2

    @staticmethod
    def answers_to_question_count(db: Connection) -> list:  # list[tuple[id, float]]
        return db.execute("SELECT question_id COUNT(question_id) as c FROM answers "
                          "GROUP BY question_id HAVING c > 1 ORDER BY question_id").fetchall()

    @staticmethod
    def average_answer_count(db: Connection) -> float:
        answers = AkinationAlgorithms.answers_to_question_count(db)

        value_sum = 0
        for answer in answers:
            value_sum += answer[1]

        return float(value_sum) / float(len(answers))

    @staticmethod
    def get_rating_increase(true_answer: float, given_answer: float) -> float:
        if true_answer == 0.0:
            return AkinationAlgorithms.no_answer_constant

        tmp = true_answer * given_answer

        if tmp > 0:  # same signs
            return (1.0 - abs(abs(true_answer) - abs(given_answer))) * AkinationAlgorithms.good_answer_weight

        else: # tmp < 0  == diff signs
            return (abs(abs(true_answer) - abs(given_answer)) - 1.0) * AkinationAlgorithms.bad_answer_weight

    @staticmethod  # no way to optimise
    def get_rating_increasemany(true_answers: list, given_answers: list) -> float:
        # true answers and given answers are of different size !!! => zip cannot be used

        increase = 0.0

        for given_answer in given_answers:
            for true_answer in true_answers:
                if given_answer[0] == true_answer[0]: # same question id
                    increase += AkinationAlgorithms.get_rating_increase(true_answer[1], given_answer[1])
                    break

        return increase

    @staticmethod
    def increase_rating(db: Connection, last_answer: GivenAnswer, threshold: float):
        # no longer # user answer is not helpful
        #if last_answer.answer_value == 0.0:
        #    return

        entities = db.entities_answering_question(last_answer.question_id).fetchall()

        ids, ratings, answer_values = [e[0] for e in entities], [e[2] for e in entities], [e[1] for e in entities]
        new_values = list()  # list[tuple[float, int]]

        for id, rating, answer_value in zip(ids, ratings, answer_values):
            if rating < threshold:
                continue

            rating_increase = AkinationAlgorithms.get_rating_increase(answer_value, last_answer.answer_value)
            if rating_increase == 0.0:
                continue

            new_value = rating + rating_increase, id
            new_values.append(new_value)

        db.update_entity_ratings(new_values)

    @staticmethod
    def increasemany_rating(db: Connection, given_answers: list):  # list[tuple[int, float]]
        entities = db.entities_answering_many_questions([str(id) for id, value in given_answers])

        new_values = list()  # list[tuple[float, int]] as list of pairs (rating and id)

        for item in entities:
            increase = AkinationAlgorithms.get_rating_increasemany(item[2], given_answers)
            if increase == 0.0:
                continue

            new_value = item[1] + increase, item[0]
            new_values.append(new_value)

        db.update_entity_ratings(new_values)

    @staticmethod
    def best_question(db: Connection, threshold: float) -> Cursor:
        return db.question_ratings(threshold)

    @staticmethod
    def best_character(db: Connection, threshold: float) -> Cursor:
        return db.entity_ratings(threshold)


class AkinatorState(IntEnum):
    AskQuestion = 0  # "Ask a question to change entity ratings"
    MakeGuess = 1  # "Attempt to guess an entity"
    MakeLastGuess = 2  # "Attempt to guess an entity despite as there are still some possibility of user giving wrong answers"
    GiveUp = 3  # "Akinator gave up as no more guessing options available"
    # Stop = "Hard stop initiated (no longer used)"
    # Restart = "Restart probably by recreating the temporary DB and saving new results (no longer used)"
    Victory = 4  # "Akinator guessed the entity"


class Akinator():
    iteration_limit: int = 24
    start_selective_rating_increase_iteration: int = 7
    start_guess_iteration: int = 5
    guess_limit: int = 7

    guess_threshold_entity_multiplier: float = 0.85
    guess_threshold_question_multiplier: float = 1.05
    guess_threshold_minimum: float = 0.5
    leader_difference: float = 0.5

    def clear(self):
        self.state = AkinatorState.AskQuestion
        self.iteration = 0
        self.guess_count = 0
        self.guess_threshold = 0.5
        self.compute_threshold = 0.0
        self.user_answers.clear()
        self.probable_entities.clear()
        self.probable_questions.clear()
        self.wrong_entities.clear()
        self.stats_recomputed = False

    def __init__(self, theme: str, version: Version, connection_type: Connection.Type = Connection.Type.game):
        self.db = Connection(connection_type, theme, version)
        self.update = Update()

        self.state = AkinatorState.AskQuestion
        self.iteration = 0
        self.guess_count = 0

        self.stats_recomputed = False
        self.guess_threshold = 0.5
        self.compute_threshold = 0.0

        self.probable_entities = list()  # list[tuple[int, float]
        self.probable_questions = list()  # list[tuple[int]]

        self.user_answers = list()  # list[tuple[float, int]]
        self.wrong_entities = list()  # list[int]

        self.clear()

    def __del__(self):
        self.db.close()

    def __recompute_stats(self):
        if not self.user_answers:
            self.stats_recomputed = True
            return

        if self.iteration <= Akinator.start_selective_rating_increase_iteration:
            AkinationAlgorithms.increase_rating(self.db, self.user_answers[-1], -100.0)
        else:
            AkinationAlgorithms.increase_rating(self.db, self.user_answers[-1], self.compute_threshold)

        maximum, minimum = self.db.entity_min_max_rating()

        self.compute_threshold = minimum + (maximum - minimum) / 2 # * self.guess_threshold
        #minimum * self.guess_threshold + maximum * (1 - self.guess_threshold)
        print("COMPUTE THRESHOLD: ", self.compute_threshold)
        self.probable_entities = AkinationAlgorithms.best_character(self.db, self.compute_threshold).fetchall()
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

        leader_rating = self.probable_entities[0][1]
        next_rating = self.probable_entities[1][1]

        print(f"LEADER RATINGS: ({leader_rating}, {next_rating})")
        print(f"GUESS THRESHOLD: {self.guess_threshold}")

        return leader_rating - next_rating >= self.guess_threshold * Akinator.leader_difference # * \
               # self.iteration / Akinator.iteration_limit

    def mark_entity(self, id: int):
        self.db.entity_set_used(id)

    def mark_question(self, id: int):
        self.db.question_set_used(id)

    def guess(self) -> tuple:  # tuple[id, name]
        id = self.probable_entities[0][0]
        name = self.db.entity_get_name(id)
        self.mark_entity(id)
        self.guess_count += 1

        return id, name

    def last_guess(self) -> tuple:  # tuple[list[tuple[id, name]], int]
        ids = [entity[0] for entity in self.probable_entities]
        names = [self.db.entity_get_name(id) for id in ids]

        #for id in ids:
        #    self.mark_entity(id)
        #    self.guess_count += 1

        return list(zip(ids, names)), Akinator.guess_limit - self.guess_count

    def ask_question(self) -> tuple:  # tuple[id, text]
        id = self.probable_questions[0][0]
        name = self.db.question_get_text(id)
        self.mark_question(id)
        return id, name

    def choose_questions(self) -> list:  # list[tuple[id,]]
        if not self.stats_recomputed:
            self.__recompute_stats()

        self.guess_threshold *= Akinator.guess_threshold_question_multiplier

        self.probable_questions = AkinationAlgorithms.best_question(self.db, self.compute_threshold).fetchall()

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

            if self.iteration > Akinator.start_guess_iteration and self.leader_is_good():
                self.state = AkinatorState.MakeGuess
            else:
                if self.iteration >= Akinator.iteration_limit or len(self.probable_questions) == 0:
                    self.state = AkinatorState.GiveUp
                else:
                    self.state = AkinatorState.AskQuestion

        elif self.state == AkinatorState.MakeGuess:
            self.choose_questions()

            if len(self.probable_questions) == 0:
                if self.guess_count >= Akinator.guess_limit:
                    # no more questions
                    self.state = AkinatorState.GiveUp
                else:
                    self.state = AkinatorState.MakeLastGuess
            else:
                # trying next question
                self.guess_threshold = min(Akinator.guess_threshold_entity_multiplier * self.guess_threshold,
                                           Akinator.guess_threshold_minimum)
                self.state = AkinatorState.AskQuestion

        elif self.state == AkinatorState.MakeLastGuess:
            self.state = AkinatorState.GiveUp

        elif self.state == AkinatorState.Victory:
            # ends the game same as restart or stop ?
            pass

        else:  # self.state == GiveUp, Stop, etc:
            # excuse me ?
            pass

        self.iteration += 1
        self.stats_recomputed = False
