from requests import get, post, Response
from enum import Enum


# REQUEST AND RESPONSE TYPES
class RRType(Enum):
    class Request(Enum):
        class GET(Enum):
            UPDATE = "fetch_update"
            DB = "fetch_db"
            THEMES = "fetch_themes"
            ENTITY_DESC = "fetch_entity_description"
            AKINATE = "akinate"

            @staticmethod
            def all() -> tuple:
                return RRType.Request.GET.UPDATE.value, \
                       RRType.Request.GET.DB.value, \
                       RRType.Request.GET.THEMES.value, \
                       RRType.Request.GET.ENTITY_DESC.value, \
                       RRType.Request.GET.AKINATE.value

        class POST(Enum):
            UPDATE = "post_update"  # for specific theme
            THEME_SUGGESTION = "post_theme"
            ENTITY_SUGGESTION = "post_entity"

            @staticmethod
            def all() -> tuple:
                return RRType.Request.POST.UPDATE.value, \
                       RRType.Request.POST.THEME_SUGGESTION.value, \
                       RRType.Request.POST.ENTITY_SUGGESTION.value

    class Response(Enum):
        NO_CONNECTION = "connection_failed"
        DATA_FORMAT_ERROR = "data_format_error"
        DATA_PROCESSING_ERROR = "data_processing_error"
        SUCCESS = "success"

        @staticmethod
        def all() -> tuple:
            return RRType.Response.NO_CONNECTION.value, \
                   RRType.Response.DATA_FORMAT_ERROR.value, \
                   RRType.Response.DATA_PROCESSING_ERROR.value, \
                   RRType.Response.SUCCESS.value


def send_post(json: dict, address: str = "localhost:8000") -> Response:
    return post(f"http://{address}", json=json, headers={"Content-Encoding": "utf-8"})


def send_get(json: dict, address: str = "localhost:8000") -> Response:
    return get(f"http://{address}", json=json, headers={"Content-Encoding": "utf-8"})


def useful_info(response: Response) -> tuple:
    return response.status_code, response.reason, response.headers, response.json()


def print_headers_and_json(headers: {}, json: {}):
    print("HEADERS")
    for i in headers:
        print(f"\"{i}\": \"{headers[i]}\"")
    print("\nJSON")
    for i in json:
        print(f"\"{i}\": \"{json[i]}\"")
    print("\n")
