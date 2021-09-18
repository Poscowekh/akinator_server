from file_skeleton import Layouts
from file_management import FileManager, PathCreator
# from VersionClass import Version, ErrorVersion
from enum import IntEnum
from MyError import MyError, MyErrorType
from os import remove


class StatsManager():
    class Error(MyError):
        class Type(MyErrorType):
            not_enough_arguments = "Theme, version or id not provided"
            unable_to_read = "Could no read data from file"
            unable_to_write = "Could no write data from file"

        def __init__(self, error_type: Type, info=None):
            MyError.__init__(self, error_type, info=info)

        def __str__(self) -> str:
            return MyError.__str__(self)

    class Type(IntEnum):
        theme = 0
        global_server = 1
        global_client = 2
        version_server = 3
        version_client = 4
        game = 5

    def __init__(self, type_: Type, theme: str = None, version = None, id: int = None):
        self.type = type_
        self.data = dict()

        if self.type == self.Type.global_client or self.type == self.Type.global_server:
            self.path = PathCreator.global_stats()
        elif self.type == self.Type.theme:
            if theme is None:
                raise self.Error(self.Error.Type.not_enough_arguments)
            self.path = PathCreator.theme_stats(theme)
        elif self.type == self.Type.version_server or self.type == self.Type.version_client:
            if version is None:
                raise self.Error(self.Error.Type.not_enough_arguments)
            self.path = PathCreator.db_stats(theme, version)
        else:  # type = game
            if id is None:
                raise self.Error(self.Error.Type.not_enough_arguments)
            self.path = PathCreator.game_stats(id)

        self.update_data()

    def __del__(self):
        from file_management import FileManager
        if self.type == self.Type.game:
            remove(self.path)
        else:
            self.write_data()

    def update_data(self) -> dict:
        try:
            self.data = FileManager.get_json(self.path)
        except FileManager.Error:
            raise self.Error(self.Error.Type.unable_to_read)

        if self.data == dict():
            if self.type == self.Type.version_server:
                self.data = Layouts.Stats.Version.template_server.value
            elif self.type == self.Type.version_client:
                self.data = Layouts.Stats.Version.template_client.value
            elif self.type == self.Type.theme:
                self.data = Layouts.Stats.Theme.template.value
            elif self.type == self.Type.global_server:
                self.data = Layouts.Stats.Global.template_server.value
            else:
                # self.type == self.Type.global_client:
                self.data = Layouts.Stats.Global.template_client.value

            self.write_data()

        return self.data

    def write_data(self):
        try:
            FileManager.write_json(self.path, self.data)
        except FileManager.Error:
            raise self.Error(self.Error.Type.unable_to_write)
