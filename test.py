from http.server import HTTPServer, BaseHTTPRequestHandler
from http import HTTPStatus
import json


class RequestHandler(BaseHTTPRequestHandler):
    def __set_headers__(self):
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        self.__set_headers__()
        self.wfile.write(bytes(self.request))

    def do_POST(self):
        print("HEADERS")
        for i in self.headers:
            print(f"{i}: {self.headers[i]}")
        length = int(self.headers.get('content-length'))
        data = json.loads(self.rfile.read(length))
        print("JSON")
        for i in data:
            print(f"{i}: {data[i]}")
        self.__set_headers__()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        # Send allow-origin header for preflight POST XHRs.
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.send_header('Access-Control-Allow-Headers', 'content-type')
        self.end_headers()


def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, RequestHandler)
    print('serving at %s:%d' % server_address)
    httpd.serve_forever()


from ConnectionClass import Connection
from VersionClass import Version
from data_generation import DataGenerator
from random import randrange, randint
from Akinator import AkinationAlgorithms, GivenAnswer, Akinator, AkinatorState
from pandas import read_sql_query, option_context


def main(entity_count: int = 100000):
    return DataGenerator.generate_tables(test_version=Version(1,2),
                                         entity_count=entity_count,
                                         entity_to_question_ratio=0.6,
                                         #entity_to_question_ratio=[0.4, 0.45, 0.5, 0.55, 0.6, 0.65][randrange(5)],
                                         answer_count_bounds=(10, 25)
                                         #answer_count_bounds=(randint(7, 16), randint(20, 36))
                                         )


def test_entities_answering_question() -> list:
    db = DataGenerator.generate_tables("test", Version(1, 2), entity_count=7, answer_count_bounds=(1, 3), use_memory=False)
    #db = DataGenerator.generate_tables("test", Version(1, 2), entity_count=7, answer_count_bounds=(1, 3))
    #AkinationAlgorithms.increase_rating(db, GivenAnswer)

    return db.entities_answering_question(2).fetchall()


def test_creation_time(step: int, count: int):
    from data_generation import DBStatistics
    from matplotlib.pyplot import show, xlabel, ylabel, scatter
    from time import process_time

    times = list()
    my_range = range(step, step * (count + 1), step)
    counts = list(my_range)
    print("Starting calculations...")
    begin = process_time()

    for i in my_range:
        print(f"--Working with {i} entities...")
        time, result = DBStatistics.exe_time(main, i)
        times.append(time)
        result.execute("DROP TABLE entities")
        result.execute("DROP TABLE questions")
        result.execute("DROP TABLE answers")
        result.execute("VACUUM")

    print("Calculations complete.")
    print(f"Time taken: {process_time() - begin} seconds")
    #print(f"Estimated time: {0.601 / 2.0 * (float(last + step) / 10000.0)**2} seconds")
    scatter(counts, times)
    xlabel(f"{step} of entities")
    ylabel("time taken, seconds")
    show()


def akinate(db: Connection):
    from pandas import read_sql_query

    akinator = Akinator(db.theme, db.version, db.connection_type)
    print(f"AKINATOR ID: {akinator.db.id}")

    while akinator.state != AkinatorState.GiveUp and akinator.state != AkinatorState.Victory:
        akinator.next_state()
        print(f"STATE: {akinator.state.value}")

        if akinator.state == AkinatorState.AskQuestion:
            id, text = akinator.ask_question()
            print(f"QUESTION: {text}")
            answer = float(input("ANSWER: "))
            akinator.receive_answer(id, answer)

            print("DB:", read_sql_query(f"SELECT id, rating FROM entities_{akinator.db.id} "
                                        f"WHERE used=0 AND rating>={akinator.compute_threshold - 1.0}", akinator.db), "\n")

        elif akinator.state == AkinatorState.MakeGuess:
            id, name = akinator.guess()
            print(f"GUESS: {name}")
            answer = float(input("ANSWER: "))
            boolean = True if answer == 1.0 else False
            akinator.receive_guess(id, boolean)
            print("\n")

        elif akinator.state == AkinatorState.MakeLastGuess:
            ids_and_names, count = akinator.last_guess()
            there_is_right = False

            for id, name in zip(ids_and_names, range(count if count <= 4 else 4)):
                print(f"LAST GUESS: {name}")
                answer = float(input("ANSWER: "))
                boolean = True if answer == 1.0 else False
                if boolean:
                    there_is_right = True
                    akinator.state = AkinatorState.Victory
                print("\n")


def test_game_connection():
    parent_db = Connection(Connection.Type.server, "test", Version(1, 3))

    """
    parent_db.insertmany_entities([("Alex", 0.0, "First entity", 0),
                                   ("Andrew", 0.0, "Second entity", 0),
                                   ("Ilyas", 0.0, "'dead inside'x1000", 0),
                                   ("Masha", 0.0, "Bad fantasy", 0)])
    

    parent_db.insertmany_entities([("Artyom", 0.0, "", 0),
                                   ("Alexander", 0.0, "", 0),
                                   ("Sergey", 0.0, "", 0),
                                   ("Valentina", 0.0, "", 0),
                                   ("Ksenya", 0.0, "", 0),
                                   ("Svetlana", 0.0, "", 0)])
    """

    #parent_db.execute("DROP TABLE questions")

    """
    parent_db.insertmany_questions([("Is your entity male?",),
                                    ("Is your entity real?",),
                                    ("Is your entity a student?",),
                                    ("Does your entity have a job?",),
                                    ("Is your entity's hair dark?",),
                                    ("Is your entity tall?",),
                                    ("Does your entity have a partner?",)#,
                                    #("Is your entity a rock star?",),
                                    #("Was your entity known for murder?",)
                                    ])
    """

    #parent_db.execute("DROP TABLE answers")

    """
    parent_db.insertmany_answers(
        [(1, 1, 1.0), (2, 1, 1.0), (3, 1, 1.0), (4, 1, -1.0), (5, 1, 1.0), (6, 1, 1.0), (7, 1, 1.0), (8, 1, -1.0),
         (9, 1, -1.0), (10, 1, -1.0), # gender answers
         (1, 2, 1.0), (2, 2, 1.0), (3, 2, 1.0), (4, 2, -1.0), (5, 2, 1.0), (6, 2, 1.0), (7, 2, -1.0), (8, 2, -1.0),
         (9, 2, -1.0), (10, 2, 1.0), # reality answers
         (1, 3, 1.0), (2, 3, 1.0), (3, 3, 1.0), (4, 3, 1.0), (5, 3, -1.0), (6, 3, -1.0), (10, 3, -1.0), # student
         (1, 4, -1.0), (2, 4, 1.0), (3, 4, -1.0), (4, 4, 1.0), (6, 4, 1.0), (9, 4, -1.0), (10, 4, 1.0), # job
         (1, 5, 1.0), (2, 5, 1.0), (3, 5, 1.0), (4, 5, -1.0), (5, 5, -1.0), (6, 5, -1.0), (7, 5, -1.0),
         (8, 5, -1.0), (10, 5, -1.0), # black hair
         (2, 6, 1.0), (3, 6, 1.0), (4, 6, -1.0), (5, 6, 1.0), (6, 6, 1.0), (7, 6, 1.0),
         (8, 6, -1.0), (10, 6, -1.0), (9, 6, 1.0),  # tall
         (1, 7, -1.0), (2, 7, 1.0), (3, 7, -1.0), (4, 7, -1.0), (6, 7, 1.0), (7, 7, 1.0), (10, 7, -1.0),
         (9, 7, 1.0)# partner
         ])
    """


    #print(parent_db)

    #cursor = parent_db.get_entities()

    game_db = Connection(Connection.Type.game, parent_db.theme, parent_db.version)

    akinate(game_db)

    #db = Connection(Connection.Type.game, "test", Version(1, 2))
    #print(db)


def auto_akinate(akinator: Akinator, chosen_entity_id: int) -> tuple:  # tuple[bool, int]
    answers = akinator.db.get_answers(["question_id", "answer_value"], f"entity_id={chosen_entity_id}").fetchall()

    question_ids, answer_values = [a[0] for a in answers],[a[1] for a in answers]

    while akinator.state != AkinatorState.GiveUp and akinator.state != AkinatorState.Victory:
        akinator.next_state()

        if akinator.state == AkinatorState.AskQuestion:
            asked_id, text = akinator.ask_question()
            answer = 0.0

            for existing_id, existing_answer in zip(question_ids, answer_values):
                if existing_id == asked_id:
                    answer = existing_answer
                    break

            akinator.receive_answer(asked_id, answer)

        elif akinator.state == AkinatorState.MakeGuess:
            guessed_id, name = akinator.guess()
            boolean = True if guessed_id == chosen_entity_id else False
            akinator.receive_guess(guessed_id, boolean)

        elif akinator.state == AkinatorState.MakeLastGuess:
            ids_and_names, count = akinator.last_guess()

            for id, name, i in zip(ids_and_names, range(count if count <= 4 else 4)):
                if id == chosen_entity_id:
                    akinator.state = AkinatorState.Victory
                    break

    print("AKINATED")

    if akinator.state == AkinatorState.Victory:
        return True, akinator.iteration
    elif akinator.state == AkinatorState.GiveUp:
        return False, akinator.iteration
    else:
        raise RuntimeError()


def auto_test_akinator(count: int) -> tuple:  # tuple[float, list]
    disk_db = DataGenerator.generate_tables("test", Version(1, 4), use_memory=False, entity_count=250,
                                            entity_to_question_ratio = 0.5, answer_count_bounds = (7, 14))

    disk_db = Connection(Connection.Type.server, "test", Version(1, 4))

    from data_generation import DBStatistics
    print(DBStatistics.average_answer_value(disk_db))

    entities = disk_db.get_entities(["id"]).fetchall()
    success_count= 0
    success_list = list()

    for i in range(count):
        akinator = Akinator(disk_db.theme, disk_db.version, Connection.Type.game)
        entity_id = entities[randint(0, len(entities) - 1)][0]
        success, iteration = auto_akinate(akinator, entity_id)
        if success:
            success_count += 1
        success_list.append((entity_id, success, iteration))

    return float(success_count) / float(count), success_list


if __name__ == '__main__':
    """test_count = 1
    success_rate, success_list = auto_test_akinator(test_count)
    print(f"Success rate is {success_rate}")
    print("{:<6}{:<8}{}".format("ID", "Success", "Iteration"))
    for e_id, success, iteration in success_list:
        print("{:<6}{:<8}{}".format(e_id, success, iteration))"""

    """from bot_db import BotDB
    from BotAkinator import BotAkinator
    bot_db = BotDB()
    chat_id = bot_db.execute("SELECT chat_id FROM users").fetchone()[0]
    akinator = BotAkinator("test", Version(1, 3), chat_id)
    print(akinator.game_db.entities_answering_many_questions([1]))"""

    from statistics import mean
    from math import log, tanh
    from matplotlib.pyplot import scatter, show, xlabel, ylabel

    def sign(a):
        return 1.0 if a >= 0 else -1.0

    def f(a, b, multiplier):
        return a - b

    def new_a_for_list(a_, B, multiplier, approx_const):
        from math import tanh
        a = a_
        for b in B:
            a -= sign(a) * f(a, b, multiplier)
        return a / multiplier

    def random_b_list(count, value_distribution):
        from random import randrange, seed
        from datetime import datetime
        seed(datetime)
        result = list()
        max = len(value_distribution)
        for i in range(count):
            result.append(value_distribution[randrange(0, max)])
        return result


    a = 1.0
    multiplier = 2.0
    approximation_constant = 0.39 / 0.75 / 200.0
    value_distribution = [1.0, 1.0, 0.5, 0.5, -0.5, -0.5, -1.0, 1.0]
    value_distribution = [-1 * value for value in value_distribution]

    count_b = 100

    approx_b = mean(random_b_list(count_b, value_distribution))
    approx_a = (approx_b + a) / 2

    #scatter(approx_b, approx_a, color="blue")

    print(f"mean of B = {mean(value_distribution)}, approx b = {approx_b}, approx a = {approx_a}")

    """sigma = "\u03C3"
    delta = "\u0394"
    xlabel(f"b")
    ylabel(f"a")"""

    #show()