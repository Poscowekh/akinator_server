from ConnectionClass import Connection
from file_management import PathCreator
from theme_db import ThemeDB
from VersionClass import Version
from pathlib import Path


"""
new_data_item = {
    theme: {
        new_entities: [],
        new_questions: [],
        new_answers: [],
        mod_answers: []
    }
}
new_data = [new_data_item]
"""

"""
QUERIES USED

pop_changes = "SELECT COUNT(entity_id) as pop_change, entity_id " \
              "FROM new_entities " \
              "WHERE chat_id IN ({}) AND theme==? AND entity_id IS NOT NULL"

distinct_names = "SELECT DISTINCT name " \
                 "FROM new_entities " \
                 "WHERE chat_id IN ({}) AND entity_id IS NOT NULL AND theme==?"

new_entities = "SELECT e.name, e.description " \
               f"FROM ({distinct_names}) d " \
               "JOIN new_entities e " \
               "ON e.name==d.name " \
               "GROUP BY name"

distinct_texts = "SELECT DISTINCT text " \
                 "FROM new_questions " \
                 "WHERE chat_id IN ({}) AND question_id IS NULL AND theme==?"

new_entities_ids = "SELECT e.tmp_entity_id AS entity_id, e.name AS name " \
                   "FROM new_entities e " \
                   f"JOIN ({distinct_names}) d " \
                   "ON e.name==d.name " \
                   "GROUP BY name"

new_question_ids = "SELECT q.tmp_question_id AS question_id, q.text AS text " \
                   "FROM new_questions q " \
                   f"JOIN ({distinct_texts}) d " \
                   "ON q.text==d.text " \
                   "GROUP BY text"

new_answers = "SELECT e.name AS name, e.entity_id AS entity_id, q.question_id AS question_id, " \
              "q.text AS text, a.answer_value AS answer_value " \
              "FROM new_answers a" \
              f"JOIN ({new_entities_ids}) e " \
              "ON e.entity_id==a.tmp_entity_id " \
              f"JOIN ({new_question_ids}) q " \
              "ON q.question_id==a.tmp_question_id " \
              "GROUP BY entity_id, question_id"

new_answers_avg = "SELECT n.name AS name, n.text AS text, AVG(a.answer_value) AS answer_value " \
                  "FROM new_answers a " \
                  f"JOIN ({new_answers}) n " \
                  "ON n.question_id==a.tmp_question_id AND n.entity_id==a.tmp_entity_id " \
                  "GROUP BY name, text"

distinct_existing_answers = "SELECT DISTINCT entity_id, question_id " \
                            "FROM new_answers " \
                            "WHERE entity_id IS NOT NULL AND question_id IS NOT NULL AND chat_id IN ({})"

mod_answers = "SELECT AVG(a.answer_value) AS average_answer_value, " \
              "a.entity_id AS entity_id, a.question_id AS question_id " \
              "FROM new_answers a " \
              f"JOIN ({distinct_existing_answers}) d " \
              "ON a.question_id==d.question_id AND a.entity_id==d.entity_id " \
              "GROUP BY entity_id, question_id"
"""


def bin_search(values: list, item: tuple) -> int:
    first = 0
    last = len(values) - 1
    pos = -1
    found = False

    while first <= last and not found:
        pos = 0
        midpoint = (first + last) // 2

        if values[midpoint][0] == item[0]:
            pos = midpoint
            found = True
        else:
            if item[0] < values[midpoint][0]:
                last = midpoint-1
            else:
                first = midpoint+1

    if found:
        return pos
    else:
        return -1


def latest_version(theme: str) -> Version:
    theme_db = ThemeDB()
    last_version = theme_db.latest_version(theme)
    theme_db.close()

    return last_version


def update_version(theme: str) -> Version:
    version = latest_version(theme)

    if version == Version(0, 0, 0):
        version = Version(1, 0, 0)

    elif not version.micro:
        version.micro = 1

    else:
        if version.micro == 19:
            version.minor += 1
            version.micro = 1
        else:
            version.micro += 1

    return version


def apply_update(new_data: dict):
    theme_db = ThemeDB()

    for theme, update in new_data.items():
        last_version = Version(0,0,0)
        old_db = None

        if theme_db.theme_exists(theme) == -1:  # new theme
            theme_db.create_new_theme(theme, Version(1, 0, 0))

        else:
            last_version = latest_version(theme)

            if last_version == Version(0,0,0):
                old_db = Connection(Connection.Type.server, theme, last_version)
                theme_db.create_new_version(theme, update_version(theme))

            else:
                old_db = Connection(Connection.Type.server, theme, last_version)
                last_version = update_version(theme)
                theme_db.create_new_version(theme, last_version)

        #Path(theme_db.db_path(theme, latest_version(theme))).mkdir(parents=True, exist_ok=True)

        server_db = Connection(Connection.Type.server, theme, latest_version(theme))
        server_db.__create_tables__()

        if old_db is not None:  # get values from old db
            entities = old_db.get_entities(["name", "base_rating", "description", "popularity"]).fetchall()
            questions = old_db.get_questions(["text"]).fetchall()
            answers = old_db.get_answers(["entity_id", "question_id", "answer_value"]).fetchall()
            old_db.close()

            server_db.insertmany_entities(entities)
            server_db.insertmany_questions(questions)
            server_db.insertmany_answers(answers)

        #server_db.update_base_ratings(new_data[theme]["pop_changes"])

        entity_ids = list()
        for name, desc in new_data[theme]["new_entities"]:
            entity_ids.append((name, server_db.insert_new_entity(name, desc)))

        question_ids = list()
        for text in new_data[theme]["new_questions"]:
            question_ids.append((text[0], server_db.insert_new_question(text)))

        for name, text, answer_value in new_data[theme]["new_answers"]:
            entity_id = server_db.get_entities(["id"], f"name=='{name}'").fetchone()[0]
            question_id = server_db.get_questions(["id"], f"text=='{text}'").fetchone()[0]
            server_db.insert_answer(entity_id, question_id, answer_value)

        #server_db.update_answers(new_data[theme]["mod_answers"])

        server_db.close()

    theme_db.close()
