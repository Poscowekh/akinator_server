# Contains file skeletons, helper classes and functions
#
# Usable paths:
# /data/theme/version/file.db
# /data/theme/version/stats.json
# /data/theme/theme_stats.json  WIP
# /data/global_stats.json  WIP
# /data/theme/updates/number.db or .json  WIP


from enum import Enum


# Templates and schemas for JSON objects and SQL tables
class Layouts():
    class BotData():
        @staticmethod
        def payload(poll_message, question, answers, chat_id, user_id, additional_info: str = None) -> dict:
            return {
                poll_message.poll.id: {
                    "question": question,
                    "answers": answers,
                    "message_id": poll_message.message_id,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "additional_info": additional_info
                }
            }

    class Table(Enum):
        themes = """themes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            string TEXT NOT NULL,
            latest_version_id INTEGER NOT NULL,
            popularity INTEGER(0) NOT NULL
        )"""
        versions = """versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER NOT NULL,
            major INTEGER(1) NOT NULL,
            minor INTEGER(0) NOT NULL,
            micro INTEGER,
            path TEXT NOT NULL,
            creation_date timestamp NOT NULL,
            popularity INTEGER(0) NOT NULL,
            available INTEGER(1) NOT NULL CHECK(available IN (0, 1)),
            FOREIGN KEY(theme_id) REFERENCES themes(id)
        )"""

        # BOT DB TABLES
        users = """users(
            chat_id INTEGER PRIMARY KEY,
            last_action TEXT NOT NULL,
            theme TEXT,
            latest_update_theme TEXT,
            iteration INTEGER(0),
            state INTEGER(0),
            language TEXT,
            id_in_poll INTEGER,
            game_started INTEGER(0) NOT NULL CHECK(game_started IN (0, 1)),
            session_date timestamp NOT NULL,
            last_update_id INTEGER(0) NOT NULL
        )"""
        given_answers = """given_answers(
            chat_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value FLOAT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )"""
        wrong_guesses = """wrong_guesses(
            chat_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )"""

        # BOT UPDATES TO ENTITY DB TABLES
        updates = """updates(
            id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            theme TEXT,
            is_complete INTEGER(0) CHECK(is_complete IN (0, 1)),
            last_tmp_entity_id INTEGER(0) NOT NULL,
            last_tmp_question_id INTEGER(0) NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )"""
        entity_updates = """new_entities(
            chat_id INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            tmp_entity_id INTEGER NOT NULL,
            entity_exists INTEGER(0) CHECK(entity_exists IN (0, 1)),
            entity_id INTEGER,
            name TEXT,
            description TEXT,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id),
            FOREIGN KEY(update_id) REFERENCES updates(id)
        )"""  # IDEA: SELECT * FROM users WHERE column LIKE '%mystring%' for name
        question_updates = """new_questions(
            chat_id INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            tmp_question_id INTEGER NOT NULL,
            question_exists INTEGER(0) CHECK(question_exists IN (0, 1)),
            question_id INTEGER,
            text TEXT,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id),
            FOREIGN KEY(update_id) REFERENCES updates(id)
        )"""
        answer_updates = """new_answers(
            chat_id INTEGER NOT NULL,
            update_id INTEGER NOT NULL,
            tmp_entity_id INTEGER NOT NULL,
            tmp_question_id INTEGER NOT NULL,
            answer_exists INTEGER(0) CHECK(answer_exists IN (0, 1)),
            answer_value FLOAT CHECK(answer_value>=-1.0 AND answer_value<=1.0 AND answer_value!=0.0),
            entity_id INTEGER,
            question_id INTEGER,
            existing_answer_value FLOAT CHECK(existing_answer_value>=-1.0 AND existing_answer_value<=1.0 AND existing_answer_value!=0.0),
            FOREIGN KEY(chat_id) REFERENCES users(chat_id),
            FOREIGN KEY(update_id) REFERENCES updates(id),
            FOREIGN KEY(tmp_entity_id) REFERENCES new_questions(tmp_entity_id),
            FOREIGN KEY(tmp_question_id) REFERENCES new_questions(tmp_question_id)
        )"""  # IDEA: SELECT * FROM users WHERE column LIKE '%mystring%' for name

        # ENTITIES DB TABLES
        entities_server = """entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_rating FLOAT(0.0) NOT NULL,
            description TEXT NOT NULL,
            wiki_link TEXT,
            popularity INTEGER(0) NOT NULL
        )"""
        entities_client = """entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_rating FLOAT(0.0) NOT NULL,
            description TEXT NOT NULL
        )"""
        questions = """questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )"""
        answers = """answers (
            entity_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value FLOAT NOT NULL CHECK(answer_value>=-1.0 AND answer_value<=1.0 AND answer_value!=0.0),
            FOREIGN KEY(entity_id) REFERENCES entities(id),
            FOREIGN KEY(question_id) REFERENCES questions(id)
            CONSTRAINT id PRIMARY KEY(entity_id, question_id)
        )"""

        @staticmethod
        def entities_game(connection_id: int) -> str:
            return f"""entities_{connection_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating FLOAT(0.0) NOT NULL,
                used INTEGER(0) NOT NULL CHECK (used IN (0, 1))
            )"""

        @staticmethod
        def questions_game(connection_id: int) -> str:
            return f"""questions_{connection_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating FLOAT(0.0) NOT NULL,
                used INTEGER(0) NOT NULL CHECK (used IN (0, 1))
            )"""

        @staticmethod
        def answers_game(connection_id: int) -> str:
            return f"""answers_{connection_id} (
                entity_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_value FLOAT NOT NULL CHECK (answer_value>=-1.0 AND answer_value<=1.0 AND answer_value!=0.0),
                FOREIGN KEY(entity_id) REFERENCES entities_{connection_id}(id),
                FOREIGN KEY(question_id) REFERENCES questions_{connection_id}(id)
            )"""

    # Do stats need schema? Takes time to check => probably no
    class Stats():
        class Global(Enum):
            template_server = {
                "program_version": dict(),
                "themes": list()
            }
            template_client = {
                "server_address": "",
                "program_version": dict(),
                "themes": list()
            }

        # server only
        class Theme(Enum):
            template = {
                "update_time": "",
                "latest_version": dict(),
                "unsupported_versions": list(dict())
            }

        class Version(Enum):
            template_server = {
                "entities_count": 0,
                "questions_count": 0,
                "answers_count": 0,
                "total_downloads": 0,
                "total_games_played": 0
            }
            template_client = {
                "entities_count": 0,
                "questions_count": 0,
                "answers_count": 0,
                "total_games_played": 0
            }

        class Game(Enum):
            template_list = {"connection_id": list()}
            template_record = {
                "entities_count": 0,
                "questions_count": 0,
                "answers_count": 0
            }

    class RequestAndResponse(Enum):
        template = {
            "request_type": "",
            "theme": "",
            "version": dict(),
            "data": dict()
        }
        #general schema without data subschema
        schema = {
            "type": "object",
            "properties": {
                "request_type": {"type": "string"},
                "theme": {"type": "string"},
                "version": {
                    "type": "object",
                    "properties": {
                        "major": {"type": "integer"},
                        "minor": {"type": "integer"},
                        "micro": {"type": "integer"}
                    },
                    "required": ["major", "minor"]
                },
                "data": {"type": "object"}
            },
            "required": ["request_type"]
        }

    class Data():
        class ServerError(Enum):
            template = {
                "error_type": "",
                "message": "",
                "additional_info": dict()
            }
            schema = {
                "type": "object",
                "properties": {
                    "error_type": {"type": "string"},
                    "message": {"type": "string"},
                    "additional_info": {"type": "object"},
                    "required": ["error_type"]
                }
            }

        class Akinate(Enum):
            template = {
                "akinator_state": "",
                "iteration": 0,
                "used_entities": list,
                "questions_and_answers": list
            }
            schema = {
                "type": "object",
                "properties": {
                    "akinator_state": {
                        "type": "string",
                        "required": True
                    },
                    "iteration": {"type": "integer"},
                    "used_entities": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "questions_and_answers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "integer"},
                                "answer": {"type": "number"}
                            }
                        }
                    }
                }
            }

        class AkinationResult(Enum):
            # may be give multiple questions
            template = {
                "akinator_state": "",
                "suggested_entities": list,
                "suggested_question": ""
            }
            schema = {
                "type": "object",
                "properties": {
                    "akinator_state": {
                        "type": "string",
                        "required": True
                    },
                    "suggested_entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"}
                            }
                        }
                    },
                    "suggested_question": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "text": {"type": "string"}
                        }
                    }
                }
            }

        class Update():
            class Post(Enum):
                template = {
                    "new_entities": list(),
                    "new_questions": list(),
                    "version_stats": dict()
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "new_entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {
                                        "type": "string",
                                        "required": False
                                    }
                                },
                                "questions_and_answers": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "question_id": {"type": "integer"},
                                            "answer_value": {"type": "number"}
                                        }
                                    }
                                },
                                "new_questions_and_answers": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "question_text": {"type": "string"},
                                            "answer_value": {"type": "number"}
                                        }
                                    },
                                    "required": False
                                }
                            }
                        },
                        "new_questions": {
                            "type": "array",
                            "items": {
                                "text": {"type": "string"}
                            }
                        },
                        "version_stats": {
                            "type": "object",
                            "properties": {
                                "entity_count": {"type": "integer"},
                                "question_count": {"type": "integer"},
                                "answer_count": {"type": "integer"},
                                "total_games_played": {"type": "integer"}
                            },
                            "required": True
                        }
                    }
                }

            class Get(Enum):
                template = {
                    "entities": list(),
                    "questions": list(),
                    "answers": list(),
                    "stats": dict()
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "base_rating": {"type": "number"}
                                }
                            }
                        },
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "text": {"type": "string"}
                                }
                            }
                        },
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "entity_id": {"type": "integer"},
                                    "question_id": {"type": "integer"},
                                    "answer_value": {"type": "number"}
                                }
                            }
                        },
                        "stats": {
                            "type": "object",
                            "properties": {
                                "entity_count": {"type": "integer"},
                                "question_count": {"type": "integer"},
                                "answer_count": {"type": "integer"}
                            }
                        }
                    }
                }

        class Fetch():
            class Description(Enum):
                template = {"text": ""}
                schema = {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"}
                    }
                }

            class Themes(Enum):
                template = {"themes": list()}
                schema = {
                    "type": "object",
                    "properties": {
                        "themes": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }

    class Object():
        class QuestionAndAnswer(Enum):
            template = {
                "id": 0,
                "answer": 0.0
            }
            schema = {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "answer": {"type": "number"}
                }
            }

        class Version(Enum):
            template = {
                "major": 0,
                "minor": 0,
                "micro": None
            }
            schema = {
                "type": "object",
                "properties": {
                    "major": {
                        "type": "integer",
                        "required": True
                    },
                    "minor": {
                        "type": "integer",
                        "required": True
                    },
                    "micro": {
                        "type": "integer",
                        "required": False
                    }
                }
            }

        class New():
            class Entity(Enum):
                template = {
                    "name": "",
                    "description": "",
                    "questions_and_answers": list(),
                    "new_questions_and_answers": list()
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {
                            "type": "string",
                            "required": False
                        },
                        "questions_and_answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question_id": {"type": "integer"},
                                    "answer_value": {"type": "number"}
                                }
                            }
                        },
                        "new_questions_and_answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "answer_value": {"type": "number"}
                                }
                            },
                            "required": False
                        },
                    }
                }

            class Question(Enum):
                template = {
                    "id": 0,
                    "text": ""
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "text": {"type": "string"}
                    }
                }

            class Answer(Enum):
                template = {
                    "question_id": 0,
                    "entity_id": 0,
                    "answer": 0.0
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "integer"},
                        "entity_id": {"type": "integer"},
                        "answer": {"type": "number"}
                    }
                }

            class QuestionAndAnswer(Enum):
                template = {
                    "id": "",
                    "answer": 0.0
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "answer": {"type": "number"}
                    }
                }

            class NewQuestionAndAnswer(Enum):
                template = {
                    "text": "",
                    "answer": 0.0
                }
                schema = {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "answer": {"type": "number"}
                    }
                }
