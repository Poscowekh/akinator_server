from re import split as re_split
from MyError import MyError, MyErrorType
from file_skeleton import Layouts


class Version():
    class Error(MyError):
        class Type(MyErrorType):
            substring_count = "Too many or too few substrings in version string"
            can_not_cast_to_int = "Parts of substring are not integer or can not be casted to it"
            comparison_error = "Uncomparable versions: different format"
            no_major_and_minor = "Major and minor arguments not provided"
            impossible_integers = "Integers used in version are less than zero or are all equal to zero"

        def __init__(self, error_type: Type, message: str = None, major: int = None, minor: int = None,
                     micro: int = None, string: str = None, dict_: dict = None,
                     second_version: str = None, printable=None):
            info = dict()
            if string is not None:
                info["string"] = string
            if major is not None and minor is not None:
                info["major"] = major
                info["minor"] = minor
                if micro is not None:
                    info["micro"] = micro
            if dict_ is not None:
                info["dict"] = dict_
            if second_version is not None:
                info["second_version"] = second_version
            if printable is not None:
                info["printable"] = printable

            MyError.__init__(self, error_type, message, info)

        def __str__(self) -> str:
            return MyError.__str__(self)

    @staticmethod
    def __string_format_check__(string: str) -> list:
        split = re_split(r".", string)
        tmp = list()
        if len(split) == 2 or len(split) == 3:
            for s in split:
                try:
                    value = int(s)
                    if value < 0:
                        raise Version.Error(Version.Error.Type.impossible_integers, string=string)
                    tmp.append(value)
                except ValueError:
                    raise Version.Error(Version.Error.Type.can_not_cast_to_int, string=string)
        else:
            raise Version.Error(Version.Error.Type.substring_count, string=string)

        split = tmp
        if len(split) == 2:
            if split[0] == split[1] == 0:
                raise Version.Error(Version.Error.Type.impossible_integers, string=string)
        elif len(split) == 3:
            if split[0] == split[1] == split[2] == 0:
                raise Version.Error(Version.Error.Type.impossible_integers, string=string)

        return split

    @staticmethod
    def __dict_format_check(dict_: dict) -> list:
        # trying to get micro as integer
        try:
            micro = dict_["micro"]
            if type(micro) is not int:
                try:
                    micro = int(micro)
                except ValueError:
                    raise Version.Error(Version.Error.Type.can_not_cast_to_int, dict_=dict_)
        except KeyError:
            micro = None

        try:
            major = int(dict_["major"])
            minor = int(dict_["minor_"])
        except KeyError:
            raise Version.Error(Version.Error.Type.no_major_and_minor, dict_=dict_)
        except ValueError:
            raise Version.Error(Version.Error.Type.can_not_cast_to_int, dict_=dict_)

        if micro is not None:
            if micro < 0:
                raise Version.Error(Version.Error.Type.impossible_integers, dict_=dict_)
        if major <= 0 or minor < 0:
            raise Version.Error(Version.Error.Type.impossible_integers, dict_=dict_)

        data = list()
        data.append(major)
        data.append(minor)
        data.append(micro)
        return data

    def __init__(self, major: int = None, minor: int = None, micro: int = None, string: str = None, dict_: dict = None):
        split = list()
        if string is not None:
            split = self.__string_format_check__(string)
        elif dict_ is not None:
            split = self.__dict_format_check(dict_)

        elif major is None or minor is None:
            raise Version.Error(Version.Error.Type.comparison_error)

        else:
            self.major = major
            self.minor = minor
            self.micro = micro
            return

        if len(split) > 0:
            self.major = split[0]
            self.minor = split[1]
            if len(split) == 3:
                self.micro = split[2]

    def to_string(self) -> str:
        if self.micro is not None:
            return f"{self.major}.{self.minor}.{self.micro}"
        else:
            return f"{self.major}.{self.minor}"

    def to_dict(self) -> dict:
        data = Layouts.Object.Version.template.value
        data["major"] = self.major
        data["minor"] = self.minor
        data["micro"] = self.micro
        return data

    def to_tuple(self) -> tuple:
        return self.major, self.minor, self.micro

    def to_list(self) -> list:
        if self.micro is not None:
            return [self.major, self.minor, self.micro]
        else:
            return [self.major, self.minor]

    def __GE__(self, other) -> bool:
        if self.major >= other.major and self.minor >= other.minor:
            if type(self.micro) is type(other.micro):
                return self.micro == other.micro
            else:
                raise Version.Error(Version.Error.Type.comparison_error, second_version=other.to_string())
        return False

    def __GT__(self, other) -> bool:
        if self.major > other.major and self.minor > other.minor:
            if type(self.micro) is type(other.micro):
                return self.micro == other.micro
            else:
                raise Version.Error(Version.Error.Type.comparison_error, second_version=other.to_string())
        return False

    def __EQ__(self, other) -> bool:
        if self.major == other.major and self.minor == other.minor:
            if type(self.micro) is type(other.micro):
                return self.micro == other.micro
            else:
                raise Version.Error(Version.Error.Type.comparison_error, second_version=other.to_string())
        return False

    def __NE__(self, other) -> bool:
        return not self.__EQ__(other)
