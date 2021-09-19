from sqlite3 import Connection
from file_skeleton import Layouts
from datetime import datetime


class BotDB(Connection):
    def create_tables(self):
        self.execute("BEGIN TRANSACTION")
        # USER DATA
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.users.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.given_answers.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.wrong_guesses.value}")
        # UPDATES TO MAIN DB
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.updates.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.entity_updates.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.question_updates.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.answer_updates.value}")
        self.commit()

    def drop(self):
        drop_query = "DROP TABLE {}"
        get_tables_query = "SELECT name FROM sqlite_master WHERE type='table'"

        tables = self.execute(get_tables_query).fetchall()
        for table in tables:
            self.execute(drop_query.format(table[0]))

        self.vacuum()

    def __init__(self, path: str = "./bot/file.db", *args, **kwargs):
        Connection.__init__(self, path, timeout=10, isolation_level=None, *args, **kwargs)

    __last_update_id_subquery__: str = "SELECT last_update_id FROM users WHERE chat_id==?"
    __last_tmp_entity_id_subquery__: str = "SELECT last_tmp_entity_id FROM updates " \
                                           "WHERE chat_id==? AND " \
                                           "id==(SELECT last_update_id FROM users WHERE chat_id==?)"
    __last_tmp_question_id_subquery__: str = "SELECT last_tmp_question_id FROM updates " \
                                             "WHERE chat_id==? AND " \
                                             "id==(SELECT last_update_id FROM users WHERE chat_id==?)"

    def begin_transaction(self):
        self.execute("BEGIN TRANSACTION")

    def commit(self):
        self.execute("COMMIT")

    def vacuum(self):
        self.execute("VACUUM")

    #
    # static methods
    @staticmethod
    def __column_string__(columns) -> str:
        return ", ".join(columns)

    @staticmethod
    def __dict_from_single_query__(columns, data: tuple) -> dict:
        return dict(zip(columns, data))

    @staticmethod
    def __list_of_dict_from_queries__(columns, data: list) -> list:
        return [BotDB.__dict_from_single_query__(columns, row) for row in data]

    #
    # helper methods
    def __select__(self, table: str, chat_id: int, columns):
        return self.execute(f"SELECT {BotDB.__column_string__(columns)} FROM {table} WHERE chat_id==?", (chat_id,))

    #
    # users table
    def get_user_data(self, chat_id: int,
                      columns=("chat_id", "last_action", "theme", "iteration", "state", "game_started", "session_date")) \
            -> tuple:
        return self.__select__("users", chat_id, columns).fetchone()

    def get_user_data_dict(self, chat_id: int,
                           columns=(
                           "chat_id", "last_action" "theme", "iteration", "state", "game_started", "session_date")) \
            -> dict:
        return BotDB.__dict_from_single_query__(columns, self.get_user_data(chat_id, columns))

    def update_last_action(self, chat_id: int, last_command: str):
        self.execute("UPDATE users SET last_action=? WHERE chat_id==?", (last_command, chat_id))

    def get_last_action(self, chat_id: int) -> str:
        return self.execute("SELECT last_action FROM users WHERE chat_id==?", (chat_id,)).fetchone()[0]

    def update_session_date(self, chat_id: int):
        self.execute("UPDATE users SET session_date=? WHERE chat_id==?", (datetime.now(), chat_id))

    def update_last_session_and_last_action(self, chat_id: int, last_action):
        self.execute("UPDATE users SET last_action=?, session_date=? WHERE chat_id==?",
                     (last_action, datetime.now(), chat_id))

    def add_user(self, chat_id: int, last_action: str):
        self.execute("INSERT INTO users(chat_id, last_action, session_date, game_started, last_update_id) "
                     "VALUES(?, ?, ?, ?, 0)", (chat_id, last_action, datetime.now(), 0))

    def set_theme(self, chat_id: int, last_action: str, theme: str):
        self.execute("UPDATE users SET last_action=?, theme=?, session_date=?, game_started=? WHERE chat_id==?",
                     (last_action, theme, datetime.now(), 1, chat_id))

    def get_session_date(self, chat_id) -> datetime:
        return self.execute("SELECT session_date FROM users WHERE chat_id==?", (chat_id,)).fetchone()[0]

    # redundant? (as set_theme is used)
    def start_game(self, chat_id):
        self.execute("UPDATE users SET game_started=?, session_date=? WHERE chat_id==?",
                     (1, datetime.now(), chat_id))

    def change_state(self, chat_id: int, last_action: str, iteration: int, state: int):
        self.execute("UPDATE users SET last_action=?, iteration=?, state=?, session_date=? WHERE chat_id==?",
                     (last_action, iteration, state, datetime.now(), chat_id))

    def get_iteration_and_state(self, chat_id: int) -> tuple:
        return self.__select__("users", chat_id, ["iteration", "state"]).fetchone()

    def get_theme(self, chat_id: int) -> str:
        return self.__select__("users", chat_id, ["theme"]).fetchone()[0]

    def get_id_in_poll(self, chat_id: int) -> int:
        return self.__select__("users", chat_id, ["id_in_poll"]).fetchone()[0]

    def save_akinator_loop(self, chat_id: int, last_action: str, iteration: int, state: int, id_in_poll: int):
        self.execute("UPDATE users SET last_action=?, iteration=?, state=?, id_in_poll=? "
                     "WHERE chat_id==?", (last_action, iteration, state, id_in_poll, chat_id))

    #
    # given_answers table
    def get_given_answers(self, chat_id: int, columns=("chat_id", "question_id", "answer_value")) -> list:
        return self.__select__("given_answers", chat_id, columns).fetchall()

    def get_given_answers_dict(self, chat_id: int, columns=("chat_id", "question_id", "answer_value")) -> list:
        return BotDB.__list_of_dict_from_queries__(columns, self.get_given_answers(chat_id, columns))

    def add_given_answer(self, chat_id: int, answer_value: float):
        self.execute("INSERT INTO given_answers(chat_id, question_id, answer_value) "
                     "VALUES(?, (SELECT id_in_poll FROM users WHERE chat_id==?), ?)",
                     (chat_id, chat_id, answer_value))
        self.update_session_date(chat_id)

    def remove_last_given_answer(self, chat_id: int):
        subquery = "SELECT question_id FROM given_answers WHERE chat_id==? ORDER BY column DESC LIMIT 1"
        self.execute(f"DELETE FROM given_answers WHERE chat_id==? AND question_id==({subquery})",
                     (chat_id, chat_id))
        self.update_session_date(chat_id)

    #
    # wrong_guesses table
    def get_wrong_guesses(self, chat_id: int, columns=("chat_id", "entity_id")) -> list:
        return self.__select__("wrong_guesses", chat_id, columns).fetchall()

    def get_wrong_guesses_dict(self, chat_id: int, columns=("chat_id", "entity_id")) -> list:
        return BotDB.__list_of_dict_from_queries__(columns, self.get_wrong_guesses(chat_id, columns))

    def add_wrong_guess(self, chat_id: int):
        self.execute("INSERT INTO wrong_guesses(chat_id, entity_id) "
                     "VALUES(?, (SELECT id_in_poll FROM users WHERE chat_id==?))",
                     (chat_id, chat_id))
        self.update_session_date(chat_id)

    def remove_last_wrong_guess(self, chat_id: int):
        subquery = "SELECT entity_id FROM wrong_guesses WHERE chat_id==? ORDER BY column DESC LIMIT 1"
        self.execute(f"DELETE FROM wrong_guesses WHERE chat_id==? AND entity_id==({subquery})",
                     (chat_id, chat_id))
        self.update_session_date(chat_id)

    def victory(self, chat_id: int):
        self.execute("UPDATE users SET state=4, session_date=? WHERE chat_id==?",
                     (datetime.now(), chat_id))

    def set_latest_update_theme(self, chat_id: int, theme: str):
        self.execute("UPDATE users SET latest_update_theme=? WHERE chat_id==?", (theme, chat_id))

    def get_latest_update_theme(self, chat_id: int) -> str:
        return self.execute("SELECT latest_update_theme FROM users WHERE chat_id==?", (chat_id,)).fetchone()[0]

    def get_new_update_id(self, chat_id: int) -> int:
        self.increment_update_id(chat_id)
        return self.get_last_update_id(chat_id)

    def get_last_update_id(self, chat_id: int) -> int:
        return self.execute(BotDB.__last_update_id_subquery__, (chat_id,)).fetchone()[0]

    def increment_update_id(self, chat_id: int):
        self.execute("UPDATE users SET last_update_id=last_update_id+1 WHERE chat_id==?", (chat_id,))

    def decrement_update_id(self, chat_id: int):
        self.execute("UPDATE users SET last_update_id=last_update_id-1 WHERE chat_id==?", (chat_id,))

    def reset_last_update_id(self, chat_id: int):
        self.execute("UPDATE users SET last_update_id=1 WHERE chat_id==?", (chat_id,))

    #
    # common
    def clear_game_session(self, chat_id: int, last_action: str):  # for restart of game
        # self.begin_transaction()
        self.execute("UPDATE users "
                     "SET last_action=?, iteration=0, state=0, id_in_poll=?, game_started=0, session_date=?"
                     "WHERE chat_id==?",
                     (last_action, None, datetime.now(), chat_id))
        self.execute("DELETE FROM given_answers WHERE chat_id=?", (chat_id,))
        self.execute("DELETE FROM wrong_guesses WHERE chat_id=?", (chat_id,))
        self.update_last_session_and_last_action(chat_id, last_action)
        # self.commit()

    def clear_update(self, chat_id: int, last_action: str):  # for restart of update
        # self.begin_transaction()
        self.execute("DELETE FROM new_answers WHERE chat_id==?", (chat_id,))
        self.execute("DELETE FROM new_questions WHERE chat_id==?", (chat_id,))
        self.execute("DELETE FROM new_entities WHERE chat_id==?", (chat_id,))
        self.reset_last_update_id(chat_id)
        self.update_last_session_and_last_action(chat_id, last_action)
        # self.commit()

    def clear_whole_session(self, chat_id: int, last_action: str):
        self.execute("DELETE FROM given_answers WHERE chat_id=?", (chat_id,))
        self.execute("DELETE FROM wrong_guesses WHERE chat_id=?", (chat_id,))
        self.execute("DELETE FROM new_answers WHERE chat_id==?", (chat_id,))
        self.execute("DELETE FROM new_questions WHERE chat_id==?", (chat_id,))
        self.execute("DELETE FROM new_entities WHERE chat_id==?", (chat_id,))
        self.update_last_session_and_last_action(chat_id, last_action)

    def clear_all_updates(self):  # after processing all complete updates
        #self.begin_transaction()
        subquery = "SELECT chat_id FROM updates WHERE is_complete==1"
        self.execute(f"DELETE FROM new_answers WHERE chat_id IN ({subquery})")
        self.execute(f"DELETE FROM new_questions WHERE chat_id IN ({subquery})")
        self.execute(f"DELETE FROM new_entities WHERE chat_id IN ({subquery})")
        self.execute(f"DELETE FROM updates WHERE chat_id IN ({subquery})")
        self.execute(f"UPDATE users SET last_update_id==0 WHERE chat_id IN ({subquery})")
        #self.vacuum()
        #self.commit()

    def get_user_updates(self) -> dict:  # dict[str, dict[str, list[tuple[...]]]]
        themes_and_chat_ids = "SELECT theme, chat_id FROM updates WHERE is_complete==1 ORDER BY theme"
        themes_and_chat_ids = self.execute(themes_and_chat_ids).fetchall()

        def result_item_template() -> dict:
            return {
                    "mod_answers": list(),
                    "new_entities": list(),
                    "new_questions": list(),
                    "new_answers": list(),
                    "pop_changes": list()
            }

        result = dict()
        themes = dict()
        result_item = result_item_template()
        theme_item = list()
        current_theme = None
        i = 0
        max_i = len(themes_and_chat_ids) - 1

        for theme, chat_id in themes_and_chat_ids:
            if current_theme is None:
                current_theme = theme

            theme_item.append(str(chat_id))

            if current_theme != theme or i >= max_i:
                themes[current_theme] = theme_item
                result[current_theme] = result_item

                current_theme = theme
                theme_item = list()
                result_item = result_item_template()

            i += 1

        pop_changes = "SELECT COUNT(entity_id) as pop_change, entity_id " \
                      "FROM new_entities " \
                      "WHERE chat_id IN ({}) AND entity_id IS NOT NULL"

        distinct_names = "SELECT DISTINCT name " \
                         "FROM new_entities " \
                         "WHERE chat_id IN ({}) AND entity_id IS NULL"

        new_entities = "SELECT e.name, e.description " \
                       f"FROM ({distinct_names}) d " \
                       "JOIN new_entities e " \
                       "ON e.name==d.name " \
                       "GROUP BY e.name"

        distinct_texts = "SELECT DISTINCT text " \
                         "FROM new_questions " \
                         "WHERE chat_id IN ({}) AND question_id IS NULL"

        new_entities_ids = "SELECT e.tmp_entity_id AS entity_id, e.name AS name " \
                           "FROM new_entities e " \
                           f"JOIN ({distinct_names}) d " \
                           "ON e.name==d.name " \
                           "GROUP BY e.name"

        new_question_ids = "SELECT q.tmp_question_id AS question_id, q.text AS text " \
                           "FROM new_questions q " \
                           f"JOIN ({distinct_texts}) d " \
                           "ON q.text==d.text " \
                           "GROUP BY q.text"

        new_answers = "SELECT e.name AS name, e.entity_id AS entity_id, q.question_id AS question_id, " \
                      "q.text AS text, a.answer_value AS answer_value " \
                      "FROM new_answers a " \
                      f"JOIN ({new_entities_ids}) e " \
                      "ON e.entity_id==a.tmp_entity_id " \
                      f"JOIN ({new_question_ids}) q " \
                      "ON q.question_id==a.tmp_question_id " \
                      "GROUP BY e.entity_id, q.question_id"

        new_answers_avg = "SELECT n.name AS name, n.text AS text, AVG(a.answer_value) AS answer_value " \
                          "FROM new_answers a " \
                          f"JOIN ({new_answers}) n " \
                          "ON n.question_id==a.tmp_question_id AND n.entity_id==a.tmp_entity_id " \
                          "GROUP BY n.name, n.text"

        distinct_existing_answers = "SELECT DISTINCT entity_id, question_id " \
                                    "FROM new_answers " \
                                    "WHERE entity_id IS NOT NULL AND question_id IS NOT NULL AND chat_id IN ({})"

        mod_answers = "SELECT AVG(a.answer_value) AS average_answer_value, " \
                      "a.entity_id AS entity_id, a.question_id AS question_id " \
                      "FROM new_answers a " \
                      f"JOIN ({distinct_existing_answers}) d " \
                      "ON a.question_id==d.question_id AND a.entity_id==d.entity_id " \
                      "GROUP BY a.entity_id, a.question_id"

        for theme, ids in themes.items():
            chat_ids = ", ".join(ids)

            result[theme]["pop_changes"] = self.execute(pop_changes.format(chat_ids)).fetchall()
            result[theme]["new_entities"] = self.execute(new_entities.format(chat_ids)).fetchall()
            result[theme]["new_questions"] = self.execute(distinct_texts.format(chat_ids)).fetchall()
            result[theme]["new_answers"] = self.execute(new_answers_avg.format(chat_ids, chat_ids)).fetchall()
            result[theme]["mod_answers"] = self.execute(mod_answers.format(chat_ids)).fetchall()

        self.clear_all_updates()

        return result

    #
    # updates
    def add_update(self, chat_id: int, last_action: str):
        self.increment_update_id(chat_id)
        self.execute("INSERT INTO updates(id, chat_id, last_tmp_entity_id, last_tmp_question_id, is_complete) "
                     f"VALUES(({BotDB.__last_update_id_subquery__}), ?, ?, ?, ?)",
                     (chat_id, chat_id, 0, 0, 0))
        self.update_last_session_and_last_action(chat_id, last_action)

    def set_update_theme(self, chat_id: int, theme: str = None):
        theme_ = theme
        if theme is None:
            theme_ = self.get_latest_update_theme(chat_id)
        self.execute("UPDATE updates "
                     "SET theme=?"
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (theme, chat_id, chat_id))

    def complete_update(self, chat_id: int, last_action: str):
        self.execute("UPDATE updates "
                     "SET is_complete=1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, last_action)

    def get_new_tmp_entity_id(self, chat_id: int) -> int:
        self.execute("UPDATE updates SET last_tmp_entity_id=last_tmp_entity_id+1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
        return self.get_last_tmp_entity_id(chat_id)

    def get_last_tmp_entity_id(self, chat_id: int) -> int:
        return self.execute(BotDB.__last_tmp_entity_id_subquery__, (chat_id, chat_id)).fetchone()[0]

    def increment_last_tmp_entity_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_entity_id=last_tmp_entity_id+1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def decrement_last_tmp_entity_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_entity_id=last_tmp_entity_id-1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def reset_last_tmp_entity_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_entity_id=0 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def get_new_tmp_question_id(self, chat_id: int) -> int:
        self.execute("UPDATE updates SET last_tmp_question_id=last_tmp_question_id+1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
        return self.get_last_tmp_question_id(chat_id)

    def get_last_tmp_question_id(self, chat_id: int) -> int:
        return self.execute(BotDB.__last_tmp_question_id_subquery__, (chat_id, chat_id)).fetchone()[0]

    def increment_last_tmp_question_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_question_id=last_tmp_question_id+1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def decrement_last_tmp_question_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_question_id=last_tmp_question_id-1 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def reset_last_tmp_question_id(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_question_id=0 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def reset_last_tmp_ids(self, chat_id: int):
        self.execute("UPDATE updates SET last_tmp_entity_id=0, last_tmp_question_id=0 "
                     f"WHERE chat_id==? AND id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))

    def update_complete_count(self) -> int:
        return len(self.execute("SELECT chat_id FROM updates WHERE is_complete==1").fetchall())

    #
    # new_entities
    def add_entity(self, chat_id: int, last_action: str):
        self.increment_last_tmp_entity_id(chat_id)
        self.execute("INSERT INTO new_entities(update_id, chat_id, tmp_entity_id) "
                     f"VALUES(({BotDB.__last_update_id_subquery__}), ?, ({BotDB.__last_tmp_entity_id_subquery__}))",
                     (chat_id, chat_id, chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, last_action)

    def add_entity_existing_info(self, chat_id, last_action: str, entity_id: int):
        self.execute("UPDATE new_entities SET entity_exists=?, entity_id=? "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND entity_id==({BotDB.__last_update_id_subquery__})",
                     (1, entity_id, chat_id, chat_id, chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, last_action)

    def add_entity_name(self, chat_id: int, last_action: str, name: str):
        self.execute("UPDATE new_entities SET name=? "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (name, chat_id, chat_id, chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, last_action)

    def add_entity_desc(self, chat_id: int, last_action: str, desc: str):
        self.execute("UPDATE new_entities SET description=? "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (desc, chat_id, chat_id, chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, last_action)

    def remove_last_new_entity(self, chat_id: int):
        self.execute("DELETE FROM new_entities "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id, chat_id, chat_id))
        self.decrement_last_tmp_entity_id(chat_id)

    def remove_new_entities(self, chat_id: int):
        self.execute(f"DELETE FROM new_entities "
                     f"WHERE chat_id==? AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
        self.reset_last_tmp_entity_id(chat_id)

    #
    # new_questions
    def add_question(self, chat_id: int, latest_action: str):
        self.increment_last_tmp_question_id(chat_id)
        self.execute("INSERT INTO new_questions(update_id, chat_id, tmp_question_id) "
                     f"VALUES(({BotDB.__last_update_id_subquery__}), ?, ({BotDB.__last_tmp_question_id_subquery__}))",
                     (chat_id, chat_id, chat_id, chat_id))
        self.update_last_session_and_last_action(chat_id, latest_action)

    def add_question_existing_info(self, chat_id: int, question_id: int):
        self.execute("UPDATE new_questions SET question_exists=?, question_id=? "
                     f"WHERE chat_id==? AND tmp_question_id==({BotDB.__last_tmp_question_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (1, question_id, chat_id, chat_id, chat_id, chat_id))

    def add_question_text(self, chat_id: int, text: str):
        self.execute("UPDATE new_questions SET text=? "
                     f"WHERE chat_id==? AND tmp_question_id==({BotDB.__last_tmp_question_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (text, chat_id, chat_id, chat_id, chat_id))

    def remove_last_new_question(self, chat_id: int):
        self.execute("DELETE FROM new_questions "
                     f"WHERE chat_id==? AND tmp_question_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id, chat_id, chat_id))
        self.decrement_last_tmp_question_id(chat_id)

    def remove_new_questions(self, chat_id: int):
        self.execute(f"DELETE FROM new_questions "
                     f"WHERE chat_id==? AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
        self.reset_last_tmp_question_id(chat_id)

    #
    # new_answers
    def add_answer(self, chat_id: int):
        self.execute("INSERT INTO new_answers(update_id, chat_id, tmp_entity_id, tmp_question_id) "
                     f"VALUES(({BotDB.__last_update_id_subquery__}), ?, ({BotDB.__last_tmp_entity_id_subquery__}), "
                     f"({BotDB.__last_tmp_question_id_subquery__}))",
                     (chat_id, chat_id, chat_id, chat_id, chat_id, chat_id))

    def add_answer_existing_info(self, chat_id: int, entity_id: int, question_id: int, existing_answer_value: float):
        self.execute("UPDATE new_answers SET answer_exists=?, entity_id=?, question_id=?, existing_answer_value=? "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND tmp_question_id==({BotDB.__last_tmp_question_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (1, entity_id, question_id, existing_answer_value,
                      chat_id, chat_id, chat_id, chat_id, chat_id, chat_id))

    def add_answer_existing_once(self, chat_id: int, question_id: int, existing_answer_value: float):
        self.add_answer_existing_info(chat_id, self.get_last_tmp_entity_id(chat_id), question_id, existing_answer_value)

    def add_answer_value(self, chat_id: int, answer_value: float):
        self.execute("UPDATE new_answers SET answer_value=? "
                     f"WHERE chat_id==? AND tmp_entity_id==({BotDB.__last_tmp_entity_id_subquery__}) "
                     f"AND tmp_question_id==({BotDB.__last_tmp_question_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (answer_value, chat_id, chat_id, chat_id, chat_id, chat_id, chat_id))

    def remove_last_new_answer(self, chat_id: int):
        self.execute("DELETE FROM new_answers "
                     f"WHERE chat_id==? AND entity_id==({BotDB.__last_tmp_entity_id_subquery__}) AND "
                     f"question_id==({BotDB.__last_tmp_question_id_subquery__}) "
                     f"AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id, chat_id, chat_id, chat_id, chat_id))

    def remove_new_answers(self, chat_id: int):
        self.execute(f"DELETE FROM new_answers "
                     f"WHERE chat_id==? AND update_id==({BotDB.__last_update_id_subquery__})",
                     (chat_id, chat_id))
