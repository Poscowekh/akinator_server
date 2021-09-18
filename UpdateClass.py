from enum import Enum
from VersionClass import Version
from os import mkdir
from os.path import isdir
from ConnectionClass import database


class UpdateErrorType(Enum):
    THEME_EXISTS = "The theme directory already exists"
    VERSION_EXISTS = "The version directory already exists"
    MKDIR_FAILED = "Not enough rights to create directory"
    UNEXPECTED_UPDATE_ERROR = "During creation of update something went wrong"


class UpdateError(Exception):
    error: UpdateErrorType
    theme: str
    version: Version
    #info = None

    def __init__(self, error: UpdateErrorType, theme: str = None, version: Version = None, info = None):
        Exception.__init__(self)
        self.error = error
        self.theme = theme
        self.version = version
        #self.info = info


def new_theme(theme: str):
    if isdir(f"./data/{theme}"):
        raise UpdateError(UpdateErrorType.THEME_EXISTS, theme)
    else:
        try:
            mkdir(f"./data/{theme}/1.0")
        except:
            raise UpdateError(UpdateErrorType.MKDIR_FAILED, theme)
        database(theme, Version(1,0))

def new_version(theme: str, version: Version):
    path = f"./data/{theme}/{version.to_string()}"
    if isdir(path):
        raise UpdateError(UpdateErrorType.VERSION_EXISTS, theme, version)
    else:
        try:
            mkdir(path)
        except:
            raise UpdateError(UpdateErrorType.MKDIR_FAILED, theme, version)
        database(theme, version)
