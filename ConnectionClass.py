from sqlite3 import Connection as sqlConnection, OperationalError, IntegrityError, \
    Cursor, Error as SQLError, connect as sql_connect, Row
from VersionClass import Version
from Stats import StatsManager
from MyError import MyError, MyErrorType
from enum import IntEnum
from file_management import PathCreator, FileManager, dirname
from file_skeleton import Layouts
from pandas import read_sql_query


class Connection(sqlConnection):
    class Type(IntEnum):
        server = 0
        client = 1
        game = 2

    @staticmethod
    def CT_to_ST(connection_type: Type) -> StatsManager.Type:
        if connection_type == Connection.Type.server:
            return StatsManager.Type.version_server
        elif connection_type == Connection.Type.client:
            return StatsManager.Type.version_server

    class Error(MyError):
        class Type(MyErrorType):
            sql_error = "SQLite3 error"
            stats_error = "Stats file manager error"
            table_error = "SQLite table error"
            arguments_error = "SQLite3 could not execute query with this set of arguments"
            missing_args_error = "Missing required arguments to execute query"

        def __init__(self, error_type: Type, stats_error: StatsManager.Error = None,
                     sql_error = None, sql_query: str = None, values: list = None,
                     add_info: dict = None):
            message = str()
            info = dict()

            if stats_error is not None:
                message = stats_error.message
                info = stats_error.info
            elif sql_error is not None:
                message = sql_error.__cause__ or sql_error.__context__
                info = sql_error.__dict__

            # additional info
            if sql_query is not None:
                info["sql_query"] = sql_query
            if values is not None:
                info["values"] = values
            if add_info is not None:
                info = dict(add_info, **info)

            MyError.__init__(self, error_type, message, info)

        def __str(self) -> str:
            return MyError.__str__(self)

    max_id: int = 1000000
    latest_id: int = 0

    def __create_table__(self, table: str):
        self.execute(f"CREATE TABLE IF NOT EXISTS {table}")

    def __create_tables__(self):
        self.begin_transaction()

        if self.connection_type is self.Type.server or self.connection_type is self.Type.client:
            if self.connection_type is self.Type.server:
                self.__create_table__(Layouts.Table.entities_server.value)
            else:
                self.__create_table__(Layouts.Table.entities_client.value)

            self.__create_table__(Layouts.Table.questions.value)
            self.__create_table__(Layouts.Table.answers.value)

        else:
            self.__create_table__(Layouts.Table.entities_game(self.id))
            self.__create_table__(Layouts.Table.questions_game(self.id))
            self.__create_table__(Layouts.Table.answers_game(self.id))

        self.commit()

    def __init__(self, connection_type: Type, theme: str, version: Version, path: str = None):
        self.connection_type = connection_type
        if self.connection_type is self.Type.game:
            if self.latest_id >= self.max_id:
                self.latest_id = 0
            self.id = self.latest_id
            self.latest_id += 1
        else:
            # server and client db connections do not have ids
            self.id = None

        if path is None:
            if connection_type != self.Type.game:
                path = PathCreator.db(theme, version)
                FileManager.makedir(dirname(path))
            else:
                path = ":memory:"
        self.path = path

        sqlConnection.__init__(self, self.path, timeout=30)

        self.theme = theme
        self.version = version
        self.connection_type = connection_type
        self.parent_db = None

        self.stats = StatsManager(self.CT_to_ST(connection_type), theme, version, self.id)
        if not self.stats.data:
            self.stats.data = {}
            self.stats.write_data()

        self.__create_tables__()
        if self.connection_type == self.Type.game:
            self.parent_db = sql_connect(PathCreator.db(theme, version))
            self.__create_game_tables__()

        #self.row_factory = Row

    def __create_game_tables__(self):
        entities = self.parent_db.execute("SELECT id, base_rating from entities").fetchall()
        questions = self.parent_db.execute("SELECT id FROM questions").fetchall()
        answers = self.parent_db.execute("SELECT entity_id, question_id, answer_value FROM answers").fetchall()

        self.executemany(f"INSERT INTO entities_{self.id} (id, rating, used) VALUES(?, ?, 0)", entities)
        self.executemany(f"INSERT INTO questions_{self.id} (id, rating, used) VALUES(?, 0.0, 0)", questions)
        self.executemany(f"INSERT INTO answers_{self.id} (entity_id, question_id, answer_value) "
                         "VALUES(?, ?, ?)", answers)

    def begin_transaction(self):
        self.execute("BEGIN TRANSACTION")

    def __select__(self, table: str, columns: list = None, condition: str = None) -> Cursor:
        query = str()

        if columns is None:
            query = "SELECT * FROM "
        else:
            query = f"SELECT {', '.join(columns)} FROM "

        if self.connection_type != self.Type.game:
            query += table
        else:
            query += f"{table}_{self.id}"

        if condition is not None:
            query += f" WHERE {condition}"

        cursor = self.cursor()
        try:
            cursor = self.execute(query)
        except OperationalError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query)
        except SQLError as e:
            raise self.Error(self.Error.Type.sql_error, sql_error=e, sql_query=query)
        else:
            return cursor

    def get_entities(self, columns: list = None, condition: str = None) -> Cursor:
        return self.__select__("entities", columns, condition)

    def get_questions(self, columns: list = None, condition: str = None) -> Cursor:
        return self.__select__("questions", columns, condition)

    def get_answers(self, columns: list = None, condition: str = None) -> Cursor:
        return self.__select__("answers", columns, condition)

    def update_whole_column(self, table: str, columns: list, values: list):
        row_count = self.stats.data[f"{table}_count"]
        if not isinstance(columns[0], str) or len(columns) != len(values[0] or len(values) != row_count):
            raise self.Error(self.Error.Type.missing_args_error,
                             add_info={"table": table, "columns": columns, "values_example": values[0]})

        query = f"UPDATE {table} SET {', '.join(columns)} WHERE id=?"
        values_ = list()
        for value, id in zip(values, range(1, row_count + 1)):
            values_.append(value + (id,))

        self.begin_transaction()
        try:
            self.executemany(query, values_)
        except OperationalError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=values)
        except IntegrityError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=values)
        except SQLError as e:
            raise self.Error(self.Error.Type.sql_error, sql_error=e, sql_query=query, values=values)
        else:
            self.commit()

    def __insert__(self, table: str, columns: list, values: tuple, auto_commit: bool = True):
        if len(columns) != len(values[0]):
            raise self.Error(self.Error.Type.arguments_error)
        if not isinstance(values[0], tuple):
            values = ((value,) for value in values)

        query = str()
        if self.connection_type != self.Type.game:
            query = f"INSERT INTO {table}"
        else:
            query = f"INSERT INTO {table}_{self.id}"
        query += f"({', '.join(columns)}) VALUES({'?, ' * (len(columns) - 1)}?)"

        try:
            self.execute(query, values)
        except IntegrityError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=[values])
        except OperationalError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=[values])
        except SQLError as e:
            raise self.Error(self.Error.Type.sql_error, sql_error=e, sql_query=query, values=[values])
        else:
            if auto_commit:
                self.commit()

    def insert_entity(self,
                      # game table values:
                      rating: float = None, used: bool = None,
                      # server and client table values:
                      name: str = None, base_rating: float = None, description: str = None,
                      # server table value:
                      popularity: int = None,
                      # True to commit immediately
                      auto_commit: bool = True
                      ):
        if self.connection_type.value <= 1:  # server or client connection
            if base_rating is None or description is None or name is None:
                raise TypeError()

            if self.connection_type.server:
                if popularity is None:
                    raise TypeError()
                self.__insert__("entities",
                                ["name", "base_rating", "description", "popularity"],
                                (name, base_rating, description, popularity))
            else:
                self.__insert__("entities",
                                ["name", "base_rating", "description"],
                                (name, base_rating, description))
        else:
            if rating is None or used is None:
                raise TypeError()
            self.__insert__("entities",
                            ["rating", "used"],
                            (rating, used))

        self.stats.data["entity_count"] += 1
        self.stats.write_data()

        if auto_commit:
            self.commit()

    def insert_question(self, text: str = None, rating: float = None, used: bool = None, auto_commit: bool = True):
        if self.connection_type == self.Type.game:
            if rating is None or used is None:
                raise TypeError()
            self.__insert__("questions", ["rating", "used"], (rating, used))
        else:
            if text is None:
                raise TypeError()
            self.__insert__("questions", ["text"], (text,))

        self.stats.data["question_count"] += 1
        self.stats.write_data()

        if auto_commit:
            self.commit()

    def insert_answer(self, entity_id: int, question_id: int, answer_value: float, auto_commit: bool = True):
        self.__insert__("answers",
                        ["entity_id", "question_id", "answer_value"],
                        (entity_id, question_id, answer_value))

        self.stats.data["answer_count"] += 1
        self.stats.write_data()

        if auto_commit:
            self.commit()

    def __insertmany__(self, table: str, columns: list, values: list):
        if len(columns) != len(values[0]):
            raise self.Error(self.Error.Type.missing_args_error,
                             add_info={"table": table, "columns": columns, "values_example": values[0]})
        if not isinstance(values[0], tuple):
            values = ((value,) for value in values)

        query = str()
        if self.connection_type != self.Type.game:
            query = f"INSERT INTO {table}"
        else:
            query = f"INSERT INTO {table}_{self.id}"
        query += f"({', '.join(columns)}) VALUES({'?, ' * (len(columns) - 1)}?)"

        self.begin_transaction()
        try:
            self.executemany(query, values)
        except IntegrityError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=values)
        except OperationalError as e:
            raise self.Error(self.Error.Type.arguments_error, sql_error=e, sql_query=query, values=values)
        except SQLError as e:
            raise self.Error(self.Error.Type.sql_error, sql_error=e, sql_query=query, values=values)
        self.commit()

    def insertmany_entities(self, values: list):
        if (self.connection_type is self.Type.server and len(values[0]) != 4) or \
                (self.connection_type is self.Type.client and len(values[0]) != 3) or \
                 (self.connection_type is self.Type.game and len(values[0]) != 3):
            raise self.Error(self.Error.Type.missing_args_error, values=values)

        if self.connection_type == self.Type.server:
            if not isinstance(values[0][0], str) or not isinstance(values[0][1], float) or \
                    not isinstance(values[0][2], str) or not isinstance(values[0][3], int):
                raise TypeError()
            self.__insertmany__("entities", ["name", "base_rating", "description", "popularity"], values)
        elif self.connection_type == self.Type.client:
            if not isinstance(values[0][0], str) or not isinstance(values[0][1], float) or \
                    not isinstance(values[0][2], str):
                raise TypeError()
            self.__insertmany__("entities", ["name", "base_rating", "description"], values)
        else:
            if not isinstance(values[0][0], str) or not isinstance(values[0][1], float) or \
                    not isinstance(values[0][2], str):
                raise TypeError()
            self.__insertmany__("entities", ["name", "base_rating", "description"], values)

        self.stats.data["entities_count"] += len(values)
        self.stats.write_data()

    def insertmany_questions(self, values: list):
        if (self.connection_type.value <= 1 and len(values[0]) != 1) or \
                (self.connection_type == self.Type.game and len(values[0]) != 2):
            raise self.Error(self.Error.Type.missing_args_error, values=values)

        if self.connection_type.value <= 1:
            if isinstance(values[0][0], str):
                self.__insertmany__("questions", ["text"], values)
            else:
                raise TypeError()
        else:
            if not isinstance(values[0], int) or not isinstance(values[1], bool):
                raise TypeError()
            self.__insertmany__("questions", ["rating", "used"], values)

        self.stats.data["questions_count"] += len(values)
        self.stats.write_data()

    def insertmany_answers(self, values: list):
        if len(values[0]) != 3:
            raise self.Error(self.Error.Type.missing_args_error, values=values)

        if not isinstance(values[0][1], int) or not isinstance(values[0][1], int) or not isinstance(values[0][2], float):
            raise TypeError()
        self.__insertmany__("answers", ["entity_id", "question_id", "answer_value"], values)

        self.stats.data["answers_count"] += len(values)
        self.stats.write_data()

    def entities_answering_question(self, question_id: int) -> Cursor:
        if self.connection_type == self.Type.game:
            return self.execute("SELECT tmp.entity_id, tmp.answer_value, e.rating "
                                f"FROM (SELECT entity_id, answer_value FROM answers_{self.id} WHERE question_id={question_id}) tmp "
                                f"JOIN entities_{self.id} e ON tmp.entity_id == e.id")
        else:
            return self.execute("SELECT tmp.entity_id, tmp.answer_value "
                                f"FROM (SELECT entity_id, answer_value FROM answers WHERE question_id={question_id}) tmp "
                                f"JOIN entities ON tmp.entity_id == entities.id")

    def entities_answering_many_questions(self, question_ids: list) -> list:
        answers_subquery = "SELECT entity_id, question_id, answer_value " \
                           f"FROM answers_{self.id} " \
                           f"WHERE question_id IN ({', '.join(question_ids)}) "# \
                           #"ORDER BY entity_id"

        query = "SELECT e.id AS entity_id, e.rating AS rating, " \
                "a.question_id AS question_id, a.answer_value AS answer_value "\
                f"FROM ({answers_subquery}) a "\
                f"INNER JOIN entities_{self.id} e ON a.entity_id == e.id "\
                "WHERE e.used==0 ORDER BY a.entity_id"

        cursor: Cursor = self.execute(query)
        cursor.row_factory = Row

        # list[tuple[int, float, list[tuple[int, float]]]]
        # as list of entities with lists of their answers
        result = list()
        # tuple[int, float, list[tuple[int, float]]
        result_item = tuple()
        current_entity_id = -1

        for row in cursor:
            if current_entity_id == -1:
                current_entity_id = row["entity_id"]
                result_item = (current_entity_id, row["rating"], list())

            elif current_entity_id != row["entity_id"]:
                result.append(result_item)
                current_entity_id = row["entity_id"]
                result_item = (current_entity_id, row["rating"], list())

            # tuple[int, float]
            answer_item = (row["question_id"], row["answer_value"])
            result_item[2].append(answer_item)

        return result

    def question_ratings(self, threshold: float) -> Cursor:
        used_entities = f"SELECT id AS entity_id FROM entities_{self.id} WHERE used=1 AND rating<{threshold}"
        question_answers_count = f"SELECT question_id, COUNT(question_id) AS count FROM answers_{self.id} " \
                                 f"WHERE entity_id NOT IN ({used_entities}) " \
                                 "GROUP BY question_id HAVING count>=1"
        unused_questions = f"SELECT id AS question_id FROM questions_{self.id} WHERE used=0"

        return self.execute(f"SELECT q.question_id AS question_id FROM ({unused_questions}) q "
                            f"JOIN ({question_answers_count}) c "
                            "ON q.question_id==c.question_id "
                            "ORDER BY c.count DESC")

    def entity_ratings(self, threshold: float) -> Cursor:
        return self.execute(f"SELECT id, rating FROM entities_{self.id} WHERE used=0 AND rating>={threshold} "
                            f"ORDER BY rating DESC")

    def entity_get_name(self, id: int) -> str:
        return self.parent_db.execute(f"SELECT name FROM entities WHERE id={id}").fetchone()[0]

    def question_get_text(self, id: int) -> str:
        return self.parent_db.execute(f"SELECT text FROM questions WHERE id={id}").fetchone()[0]

    def entity_set_used(self, id: int):
        self.execute(f"UPDATE entities_{self.id} SET used=1 WHERE id=={id}")

    def question_set_used(self, id: int):
        self.execute(f"UPDATE questions_{self.id} SET used=1 WHERE id=={id}")

    def __updatemany__(self, table: str, id_name: str, columns: list, values: list):
        table_ = table
        if self.connection_type == Connection.Type.game:
            table_ = f"{table}_{self.id}"
        query = f"UPDATE {table_} SET {'=?, '.join(columns) + '=?'} WHERE {id_name}=?"
        self.executemany(query, values)

    def update_entity_ratings(self, values: list):  # values = list[..., int]
        self.__updatemany__("entities", "id", ["rating"], values)

    def entity_min_max_rating(self) -> tuple:  #tuple[float, float]
        return self.get_entities(["MAX(rating)", "MIN(rating)"], "used=0 AND rating>-10000.0").fetchone()

    def clear(self):
        if self.connection_type == Connection.Type.game:
            self.execute(f"DROP TABLE entities_{self.id}")
            self.execute(f"DROP TABLE questions_{self.id}")
            self.execute(f"DROP TABLE answers_{self.id}")
            self.stats.data = Layouts.Stats.Game.template_record.value
        else:
            self.execute(f"DROP TABLE entities")
            self.execute(f"DROP TABLE questions")
            self.execute(f"DROP TABLE answers")
            if self.connection_type == Connection.Type.server:
                self.stats.data = Layouts.Stats.Version.template_server.value
            else:
                self.stats.data = Layouts.Stats.Version.template_client.value
        self.stats.write_data()

    def __search_string__(self, table: str, column: str, string: str) -> Cursor:
        return self.__select__(table, [column], f"{column} LIKE '%{string}%'")

    def search_name(self, name: str) -> list:
        return self.__search_string__("entities", "name", name).fetchall()

    def search_text(self, text: str) -> list:
        return self.__search_string__("questions", "text", text).fetchall()

    def __str__(self) -> str:
        if self.connection_type == self.Type.game:
            return f"ENTITIES:\n{read_sql_query(f'SELECT * FROM entities_{self.id}', self)}\n\n" \
                   f"QUESTIONS:\n{read_sql_query(f'SELECT * FROM questions_{self.id}', self)}\n\n" \
                   f"ANSWERS:\n{read_sql_query(f'SELECT * FROM answers_{self.id}', self)}\n"
        else:
            return f"ENTITIES:\n{read_sql_query('SELECT * FROM entities', self)}\n\n" \
                   f"QUESTIONS:\n{read_sql_query('SELECT * FROM questions', self)}\n\n" \
                   f"ANSWERS:\n{read_sql_query('SELECT * FROM answers', self)}\n"

    def entity_count(self) -> int:
        return self.get_entities(["id"]).rowcount

    def question_count(self) -> int:
        return self.get_questions(["id"]).rowcount

    def answer_count(self) -> int:
        return self.get_answers(["entity_id"]).rowcount

    def update_base_ratings(self, ids_and_popularity_changes: list):
        query = "UPDATE entities " \
                f"SET popularity=popularity+?, base_rating=popularity/{self.entity_count()} " \
                "WHERE id==?"
        self.executemany(query, ids_and_popularity_changes)

    def update_answers(self, ids_and_values: list):
        self.create_function("ANSWER_VALUE_CHANGE", 2, Connection.answer_change)
        query = "UPDATE answers " \
                "SET answer_value=ANSWER_VALUE_CHANGE(answer_value, ?) " \
                "WHERE entity_id==? AND question_id==?"
        self.executemany(query, ids_and_values)

    @staticmethod
    def answer_change(old_value: float, average_given_value: float) -> float:
        """
        def sign(a: float) -> float:
            return 1.0 if a >= 0.0 else -1.0

        return sign(old_value - average_given_value) * abs(abs(old_value)- abs(average_given_value))
        """

        # reverted to just mean of those two
        return (old_value + average_given_value) / 2

    def insert_new_entity(self, name: str, desc: str) -> int:
        cur = self.cursor()
        cur.execute("INSERT INTO entities(name, description, base_rating, popularity) "
                    "VALUE(?, ?, 0.0, 0)", (name, desc))
        return cur.lastrowid

    def insert_new_question(self, text: str) -> int:
        cur = self.cursor()
        cur.execute("INSERT INTO questions(text) VALUE(?)", (text,))
        return cur.lastrowid


def connect(connection_type: Connection.Type, theme: str, version: Version, path: str = None) -> Connection :
    return Connection(connection_type, theme, version, path)

