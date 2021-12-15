import settings
import dataset

default = "sqlite:///videos.db"
db = dataset.connect(settings.get("db_path") or default)
table = db["videos"]
