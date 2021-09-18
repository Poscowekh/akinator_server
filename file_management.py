from jsonschema import validate, ValidationError, SchemaError
from json import load, dump, JSONDecodeError
from os import R_OK, W_OK, access, makedirs
from os.path import isfile, isdir, dirname
from MyError import MyError, MyErrorType
from VersionClass import Version


class PathCreator():
    @staticmethod
    def theme_db() -> str:
        return "./data/themes.db"

    @staticmethod
    def db(theme: str, version: Version) -> str:
        return f"./data/{theme}/{version.to_string()}/file.db"

    @staticmethod
    def db_stats(theme: str, version: Version) -> str:
        return f"./data/{theme}/{version.to_string()}/stats.json"

    @staticmethod
    def theme_stats(theme: str) -> str:
        return f"./data/{theme}/theme_stats.json "

    @staticmethod
    def global_stats() -> str:
        return f"./data/global_stats.json"

    @staticmethod # WIP
    def update_db(theme: str, number) -> str:
        return f"./data/{theme}/{number}/.db"

    @staticmethod
    def game_stats(id: int) -> str:
        return f"./data/game/{id}_stats.json"


"""
Helper class that can:
    - read JSON from string or file
    - write JSON to string or file
    - validate JSON using schema
"""


class FileManager():
    class Error(MyError):
        class Type(MyErrorType):
            file_directory_not_found = "File directory does not exist"
            file_not_found = "File does not exist"
            file_no_read = "No rights to read from file"
            file_no_write = "No rights to write to file"
            not_json = "Data is not JSON"
            validation_data = "JSON data could not be validated using the schema"
            validation_schema = "JSON schema is not valid itself"
            system_error = "System has ran into an unknown problem"

        def __init__(self, error: Type, message: str = None, info=None, json: dict = None, schema: dict = None):
            MyError.__init__(self, error, message, info)
            self.json = json
            self.schema = schema

        def __str__(self) -> str:
            return MyError.__str__(self)


    @staticmethod
    def __try_find_path_to_file__(path: str, create_dirs: bool):
        directory = dirname(path)
        if not isdir(directory):
            if create_dirs:
                FileManager.makedir(directory)
            else:
                raise FileManager.Error(FileManager.Error.Type.file_directory_not_found,
                                        f"Directory path: {directory}")

    @staticmethod
    def __try_find_file__(path: str) -> bool:
        return isfile(path)

    @staticmethod
    def __try_access_read__(path: str):
        if not access(path, R_OK):
            raise FileManager.Error(FileManager.Error.Type.file_no_read, f"File path: {path}")

    @staticmethod
    def __try_access_write__(path: str):
        if not access(path, W_OK):
            raise FileManager.Error(FileManager.Error.Type.file_no_read, f"File path: {path}")

    @staticmethod
    def __try_read__(path: str, destination):
        with open(path, "r") as file:
            try:
                if type(destination) is str:
                    destination = file.read()
                else:
                    destination = load(file)

            except SystemError as e:
                raise FileManager.Error(FileManager.Error.Type.system_error, info=e.args)
            except OSError as e:
                raise FileManager.Error(FileManager.Error.Type.system_error, info=e.args)

            except JSONDecodeError as e:
                raise FileManager.Error(FileManager.Error.Type.not_json, message=e.msg, json=e.doc,
                                           info={"line": e.lineno, "column": e.colno})

            return destination

    @staticmethod
    def __try_write_mod__(path: str, data, mod: str):
        with open(path, mod) as file:
            try:
                if type(data) is str:
                    file.write(data)
                else:
                    dump(data, file)

            except SystemError as e:
                raise FileManager.Error(FileManager.Error.Type.system_error)
            except OSError as e:
                raise FileManager.Error(FileManager.Error.Type.system_error)

    @staticmethod
    def __convert_validation_error__(error) -> dict:
        info = dict()

        if error.cause is not None:
            info["cause"] = error.cause
        if error.context is not None:
            info["context"] = error.context
        if error.path is not None and error.schema_path is not None:
            info["path"] = error.path, error.schema_path

        return info

    @staticmethod
    def __try_validate__(json: dict, schema: dict):
        try:
            validate(json, schema)

        except ValidationError as e:
            raise FileManager.Error(FileManager.Error.Type.validation_data, message=e.message, json=json,
                                   schema=schema, info=FileManager.__convert_validation_error__(e))
        except SchemaError as e:
            raise FileManager.Error(FileManager.Error.Type.validation_schema, message=e.message, json=json,
                                   schema=schema, info=FileManager.__convert_validation_error__(e))

    @staticmethod
    def __get_data__(path: str, destination, schema: dict = None,
                     create_if_not_exists: bool = True, retry_flag: bool = False):
        try:
            if not FileManager.__try_find_file__(path):
                if create_if_not_exists:
                    FileManager.__try_write_mod__(path, dict(), "w")
                else:
                    raise FileManager.Error(FileManager.Error.Type.file_not_found)
            FileManager.__try_access_read__(path)
            destination = FileManager.__try_read__(path, destination)

        except FileManager.Error as e:
            if e.error_type == FileManager.Error.Type.system_error:
                if not retry_flag:
                    destination = FileManager.__get_data__(path, schema, retry_flag=True)
            else:
                raise

        if schema is not None:
            FileManager.__try_validate__(destination, schema)

        return destination

    # Usable funcs

    @staticmethod
    def makedir(directory: str):
        try:
            makedirs(directory, exist_ok=True)
        except SystemError as e:
            raise FileManager.Error(FileManager.Error.Type.system_error)
        except OSError as e:
            raise FileManager.Error(FileManager.Error.Type.system_error)

    @staticmethod
    def get_json(path: str, schema: dict = None, create_if_not_exists: bool = True) -> dict:
        data = dict()
        data = FileManager.__get_data__(path, data, schema, create_if_not_exists)
        return data

    @staticmethod
    def get_string(path: str, create_if_not_exists: bool = True) -> str:
        data = str()
        data = FileManager.__get_data__(path, data, create_if_not_exists=create_if_not_exists)
        return data

    @staticmethod
    def write_json(path: str, json: dict, create_if_not_exists: bool = True):
        FileManager.__try_find_path_to_file__(path, create_if_not_exists)
        if FileManager.__try_find_file__(path):
            FileManager.__try_access_read__(path)
        if create_if_not_exists:
            FileManager.__try_write_mod__(path, json, "w+")
        else:
            FileManager.__try_write_mod__(path, json, "w")

    @staticmethod
    def add_json(path: str, json: dict, create_if_not_exists: bool = True):
        FileManager.__try_find_path_to_file__(path, create_if_not_exists)
        if FileManager.__try_find_file__(path):
            FileManager.__try_access_read__(path)
        if create_if_not_exists:
            FileManager.__try_write_mod__(path, json, "a+")
        else:
            FileManager.__try_write_mod__(path, json, "a")

    @staticmethod
    def write_string(path: str, data: str, create_if_not_exists: bool = True):
        FileManager.__try_find_path_to_file__(path, create_if_not_exists)
        if FileManager.__try_find_file__(path):
            FileManager.__try_access_read__(path)
        if create_if_not_exists:
            FileManager.__try_write_mod__(path, data, "w+")
        else:
            FileManager.__try_write_mod__(path, data, "w")

    @staticmethod
    def add_string(path: str, data: str, create_if_not_exists: bool = True):
        FileManager.__try_find_path_to_file__(path, create_if_not_exists)
        if FileManager.__try_find_file__(path):
            FileManager.__try_access_write__(path)
        if create_if_not_exists:
            FileManager.__try_write_mod__(path, data, "a+")
        else:
            FileManager.__try_write_mod__(path, data, "a")
