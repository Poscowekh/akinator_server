from http.server import HTTPServer, HTTPStatus, BaseHTTPRequestHandler
from requests import Request, Response
from json import JSONDecodeError, load, loads, dumps
from jsonschema import validate, ValidationError
from file_skeleton import Schema, Template
from VersionClass import Version, VersionFormatError
from DBInterface import DBInterface
from ConnectionClass import Connection, Stats, ConnectionType
from enum import Enum
from logging import Logger
from os import walk
from io import open
from Requests import Reason
from sqlite3 import Row


class ErrorBadFormat(Exception):
    class ErrorType(Enum):
        HEADERS_INVALID = "Headers lack required parts for request"
        JSON_INVALID = "JSON data is not a proper JSON"
        JSON_SCHEMA_INVALID = "JSON validation failed, see response data for required schema"
        JSON_DATA_INVALID = "Data in JSON could not be processed"
        REQUEST_TYPE_UNSUPPORTED = "Request type is not supported by server"

    def __init__(self, type: ErrorType, message: str = None):
        Exception.__init__(self)
        self.type = type
        self.message = message


GET_REQUESTS = Reason.Request.GET.all()
POST_REQUESTS = Reason.Request.POST.all()
RESPONSES = Reason.Response.all()


class RequestHandler(BaseHTTPRequestHandler):
    request_json: {} = None
    response_json: {} = None
    log: Logger = Logger()  # found out it should log by itself: no longer needed probably
    #db: DBInterface = None

    def __check_format__(self):
        # Headers do not have important info
        if "Content-Type" not in self.headers or "Content-Length" not in self.headers or \
                "Content-Encoding" not in self.headers or self.headers["Content-Type"] is not "application/json" or \
                self.headers["Content-Encoding"] is not "utf-8":
            raise ErrorBadFormat(ErrorBadFormat.ErrorType.HEADERS_INVALID)

        try:
            self.__read_json__()
            validate(self.request_json, Schema.REQUEST_RESPONSE.value)

        except JSONDecodeError or ValueError:
            raise ErrorBadFormat(ErrorBadFormat.ErrorType.JSON_INVALID)

        except ValidationError:
            raise ErrorBadFormat(ErrorBadFormat.ErrorType.JSON_SCHEMA_INVALID)

    def __read_json__(self):
        self.request_json = loads(self.rfile.read(int(self.headers.get("Content-Length"))))

    def __respond_bad_format__(self, error: ErrorBadFormat):
        if error.
        self.__write__(Schema)
        self.send_response(HTTPStatus.BAD_REQUEST.value, error.message.value)
        self.__end_headers__()

    def __end_headers__(self):
        self.send_header("Content-Encoding", "utf-8")
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    @staticmethod
    def __search_theme__(theme: str) -> bool:
        return theme in next(walk("./data/"))[1]

    def __search_version__(self, theme: str, version: Version) -> bool:
        if self.__search_theme__(theme):
            return version.to_string() in next(walk(f"./data/{theme}/"))[1]
        return False

    def __write__(self, json: dict):
        self.wfile.write(dumps(json).encode('utf-8'))

    def __do_GET_themes__(self):
        response_data = Template.REQUEST_RESPONSE.value
        response_data["theme"] = self.request_json["theme"]
        response_data["version"] = self.request_json["version"]
        response_data["data"] = Template.Data.Fetched.THEMES.value
        response_data["data"]["themes"] = next(walk("./data/"))[1]
        self.__write__(response_data)

    @staticmethod
    def __table_to_json__(conn: DBInterface, table: str) -> dict:
        conn.row_factory = Row
        cur = conn.cursor()
        rows = cur.execute(f"SELECT * FROM {table}").fetchall()
        conn.commit()
        conn.close()
        return dumps([dict(row) for row in rows])

    def __db_to_json__(self, theme: str, version: Version) -> dict:
        conn = DBInterface(ConnectionType.SERVER.value, theme, version)
        tables = Template.Data.Update.value
        tables["entities"] = self.__table_to_json__(conn, "ENTITIES")
        tables["questions"] = self.__table_to_json__(conn, "QUESTIONS")
        tables["answers"] = self.__table_to_json__(conn, "ANSWERS")
        tables["stats"] = conn.stats.data
        return tables

    def __do_GET_update__(self, version: Version):
        response_data = Template.REQUEST_RESPONSE.value
        response_data["theme"] = self.request_json["theme"]
        latest_version = Stats(f"./data/{response_data['theme']}/theme_stats.json", ConnectionType.SERVER).data["latest_version"]

        if version.to_string() == latest_version:
            response_data["version"] = self.request_json["version"]
        else:
            response_data["version"] = latest_version
            response_data["data"] = self.__db_to_json__(response_data["theme"], version)

        self.__write__(response_data)

    def __do_GET_db__(self, version: Version):
        response_data = Template.REQUEST_RESPONSE.value
        if not self.__search_version__(self.request_json["theme"], version):
            self.__respond_bad_format__(BadFormatError(BadFormatErrorType.JSON_DATA_INVALID))
            return

        response_data["theme"] = self.request_json["theme"]
        response_data["version"] = self.request_json["version"]
        response_data["data"] = Template.Data.Update.GET.value
        response_data["data"] = self.__db_to_json__(response_data["theme"], version)
        response_data["data"].pop("stats", None)

        self.__write__(response_data)

    def __do_GET_entity_desc__(self, version: Version):
        if not self.__search_version__(self.request_json["theme"], version):
            self.__respond_bad_format__(BadFormatError(BadFormatErrorType.JSON_DATA_INVALID))
            return

        response_data = Template.REQUEST_RESPONSE.value
        response_data["theme"] = self.request_json["theme"]
        response_data["version"] = self.request_json["version"]
        response_data["data"] = Template.Data.Fetched.DESCRIPTION.value
        conn = DBInterface(ConnectionType.SERVER, response_data["theme"], version)
        response_data["data"]["text"] = conn.execute(f"SELECT description FROM ENTITIES WHERE id={self.request_json['data']['id']} LIMIT 1").fetchone()[0]
        conn.commit()
        conn.close()
        self.__write__(response_data)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        # allow_headers
        for header in ['content-type', "content-encoding", "content-length"]:
            self.send_header('Access-Control-Allow-Headers', header)
        self.end_headers()

    def do_GET(self):
        #self.log.write_to_log(f"{self.log_date_time_string()}: {self.client_address} made GET request:")
        try:
            self.__check_format__()
        except BadFormatError as e:
            self.__respond_bad_format__(e)

        request_type = self.request_json["request_type"]

        if request_type not in GET_REQUESTS:
            self.__respond_bad_format__(BadFormatError(BadFormatErrorType.REQUEST_TYPE_UNSUPPORTED))

        # now only supported requests
        version = Version()
        if request_type is not Reason.Request.GET.THEMES.value:
            try:
                version = Version(string = self.request_json["version"])
            except VersionFormatError as e:
                self.__respond_bad_format__(BadFormatError(BadFormatErrorType.JSON_DATA_INVALID))

        # methods for each of request types
        if request_type == Reason.Request.GET.THEMES.value:
            self.__do_GET_themes__()
        elif request_type == Reason.Request.GET.UPDATE.value:
            self.__do_GET_update__(version)
        elif request_type == Reason.Request.GET.DB.value:
            self.__do_GET_db__(version)


        self.__end_headers__()


class Server(HTTPServer):
    def __init__(self, host: str = "localhost", port: int = 8000):
        HTTPServer.__init__((host, port), RequestHandler)



def any():
    pass


server = HTTPServer(("localhost", 8000), BaseHTTPRequestHandler)
while True:
    server.serve_forever()

