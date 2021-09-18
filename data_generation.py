from ConnectionClass import Connection
from VersionClass import Version
#from Akinator import Akinator, AkinationAlgorithms
from random import randint, randrange
from time import process_time


class DataGenerator():
    @staticmethod
    def generate_entities(db: Connection, count: int, name_template: str = "entity_{}_name",
                          description_template: str = "entity_{}_description"):
        entities = list()

        for i in range(1, count + 1, 1):
            entities.append((name_template.format(i), 0.0, description_template.format(i), 0))

        db.insertmany_entities(entities)

    @staticmethod
    def generate_questions(db: Connection, count: int, text_template: str = "question_{}_text"):
        questions = list()

        for i in range(1, count + 1, 1):
            questions.append((text_template.format(i),))

        db.insertmany_questions(questions)

    @staticmethod
    def generate_answers(db : Connection, entity_count: int, question_count: int, important_question_count,
                         answer_count_bounds: tuple):
        answers = list()

        for i in range(1, entity_count + 1, 1):
            max = randint(answer_count_bounds[0], answer_count_bounds[1])
            for j in range(max):
                if j < important_question_count:
                    answers.append((i, j, [-1.0, 1.0][randrange(2)]))
                else:
                    non_imp_q_count = question_count - important_question_count
                    answers.append((i,
                                    randint(int(non_imp_q_count / max * (j - 1)) + important_question_count,
                                            int(non_imp_q_count / max * j) + important_question_count),
                                    [-1.0, 1.0, 1.0, 1.0][randrange(4)]))

        db.insertmany_answers(answers)

    @staticmethod
    def generate_tables(test_theme: str = "test", test_version: Version = Version(1, 0, 0),
                        entity_count: int = 10000, entity_to_question_ratio: float = 0.5,
                        answer_count_bounds: tuple = (7, 20),
                        use_memory: bool = True) -> Connection:
        db: Connection
        if use_memory:
            db = Connection(Connection.Type.server, test_theme, test_version, ":memory:")
        else:
            db = Connection(Connection.Type.server, test_theme, test_version)

        DataGenerator.generate_entities(db, entity_count)
        q_count = int(entity_count * entity_to_question_ratio)
        important_q_count = int(q_count * 0.1)
        important_q_count = important_q_count if important_q_count >= 10 else 10
        DataGenerator.generate_questions(db, q_count)
        DataGenerator.generate_answers(db, entity_count, q_count, important_q_count, answer_count_bounds)

        return db


class DBStatistics():
    @staticmethod
    def exe_time(function, *args) -> tuple:  # tuple[float, result_type]
        temp = process_time()
        result = function(*args)
        return process_time() - temp, result

    @staticmethod
    def average_answer_value(db: Connection) -> float:
        return db.execute("SELECT avg(answer_value) FROM answers").fetchone()[0]
    """
    @staticmethod
    def answers_to_question_count(db: Connection) -> list:  # list[tuple[id, float]]
        return AkinationAlgorithms.answers_to_question_count(db)

    @staticmethod
    def average_answer_count(db: Connection) -> float:
        return AkinationAlgorithms.average_answer_count(db)
    """
