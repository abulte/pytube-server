import settings
import dataset

default = "sqlite:///videos.db"
db = dataset.connect(settings.get("db_path") or default)
table = db["videos"]


def get_tags():
    tags = db.query("SELECT DISTINCT(json_each.key) FROM videos, \
                    json_each(tags)")
    return [t["key"] for t in tags]
