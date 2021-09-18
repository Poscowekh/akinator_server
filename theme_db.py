from sqlite3 import Connection
from datetime import datetime
from file_skeleton import Layouts
from VersionClass import Version
from file_management import PathCreator


class ThemeDB(Connection):
    latest_version_id_query: str = "SELECT latest_version_id FROM themes WHERE string==?"

    def drop(self):
        self.execute("DROP TABLE themes")
        self.execute("DROP TABLE versions")
        self.execute("VACUUM")

    def create_tables(self):
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.themes.value}")
        self.execute(f"CREATE TABLE IF NOT EXISTS {Layouts.Table.versions.value}")

    def __init__(self):
        Connection.__init__(self, PathCreator.theme_db(), timeout=10, isolation_level=None)

    def themes(self) -> list:
        return self.execute("SELECT string FROM themes").fetchall()

    def available_themes(self) -> list:
        subquery = "SELECT theme_id FROM versions WHERE available==1"
        query = f"SELECT string FROM themes WHERE id IN ({subquery})"
        return self.execute(query).fetchall()

    def latest_version(self, theme: str) -> Version:
        query = f"SELECT major, minor, micro FROM versions WHERE id==({ThemeDB.latest_version_id_query})"
        version_tuple = self.execute(query, (theme,)).fetchone()
        if version_tuple is None:
            return Version(0,0,0)
        return Version(version_tuple[0], version_tuple[1], version_tuple[2])

    def latest_db_path(self, theme) -> str:
        query = f"SELECT path FROM versions WHERE id==({ThemeDB.latest_version_id_query})"
        return self.execute(query, (theme,)).fetchone()[0]

    def db_path(self, theme, version: Version) -> str:
        subquery = "SELECT id FROM themes WHERE theme==?"
        query = f"SELECT path FROM versions WHERE theme_id=({subquery}) AND major==? AND minor==? AND micro==?"
        return self.execute(query, (theme,) + version.to_tuple()).fetchone()[0]

    def dbs_to_delete(self, time_limit: datetime) -> list:
        subquery = "SELECT theme_id, COUNT(theme_id) AS count FROM versions HAVING count>1"
        query = f"SELECT id, path FROM versions WHERE theme_id IN ({subquery}) AND creation_date<?"
        return self.execute(query, (time_limit,)).fetchall()

    def delete_versions(self, version_ids: list):
        values = ", ".join(version_ids)
        query = f"DELETE FROM versions WHERE id IN ({values})"
        self.execute(query)

    def set_latest_version_id(self, theme: str, id: int):
        query = "UPDATE themes SET latest_version_id=? WHERE string==?"
        self.execute(query, (id, theme))

    def create_new_version(self, theme: str, new_version: Version, available: bool = True):
        available_int = 1 if available else 0
        subquery = "SELECT id FROM themes WHERE string==?"
        query = "INSERT INTO versions(theme_id, major, minor, micro, path, creation_date, popularity, available) " \
                f"VALUES(({subquery}), ?, ?, ?, ?, ?, 0, ?)"
        values = (theme,) + new_version.to_tuple() + (PathCreator.db(theme, new_version), datetime.now(), available_int)

        cur = self.cursor()
        cur.execute(query, values)
        new_latest_version_id = cur.lastrowid
        cur.close()
        self.set_latest_version_id(theme, new_latest_version_id)
        return new_latest_version_id

    def create_new_theme(self, theme: str, first_version: Version):
        query = "INSERT INTO themes(string, latest_version_id, popularity) VALUES(?, 0, 0)"

        cur = self.cursor()
        cur.execute(query, (theme,))
        theme_id = cur.lastrowid
        cur.close()
        self.create_new_version(theme, first_version)
        return theme_id

    def theme_exists(self, theme: str) -> int:
        query = "SELECT id FROM themes WHERE string==?"
        id = self.execute(query, (theme,))
        if id is None:
            return -1
        else:
            return id