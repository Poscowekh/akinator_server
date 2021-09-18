# Used as example of created exceptions


from enum import Enum
from json import dumps, loads
from file_skeleton import Layouts


class MyErrorType(Enum):
    pass
    # usual format:
    # name = "string_value"


class MyError(Exception):
    """
        Define subclass of error type here as:
        class ErrorType(MyErrorType):
            ...
     """

    def __init__(self, error_type, message: str = None, info: dict = None):
        if not issubclass(type(error_type), MyErrorType):
            raise TypeError()
        self.error_type = error_type
        self.message = message
        self.info = info

    def __str__(self) -> str:
        string = str()
        string += f"Error type: {self.error_type.value}\n"

        if self.message is not None:
            string += f"Message: {self.message}\n"

        if self.info:
            if type(self.info) is list or type(self.info) is tuple:
                string += f"Additional info provided:\n"
                for elem in self.info:
                    string += f"    {elem}\n"
            elif type(self.info) is dict:
                string += f"Additional info provided:\n"
                for name, value in self.info.items():
                    string += f"    {name}: {value}\n"
            else:
                try:
                    info_string = str(self.info)
                except TypeError:
                    return string
                string += f"Additional info provided: {info_string}\n"

        return string

    def json(self) -> dict:
        json = Layouts.Data.ServerError.value
        json["error_type"] = self.error_type.value

        if self.message is not None:
            json["message"] = self.message
        else:
            json["message"] = ""

        if self.info:
            if type(self.info) is tuple:
                json["additional_info"] = loads(dumps(self.info))
            elif type(self.info) is list:
                json["additional_info"] = self.info
            elif type(self.info) is dict:
                json["additional_info"] = self.info
            else:
                raise TypeError()

        return json

    def print(self):
        print(self.__str__())

    def __eq__(self, other) -> bool:
        return self.error_type == other.error_type
