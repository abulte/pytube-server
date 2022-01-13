import dataset

from herotube import settings

DEFAULT_DSN = "sqlite:///videos.db"
db = dataset.connect(settings.get("database_url") or DEFAULT_DSN)
table = db["videos"]


def get_oldest_video():
    return table.find_one(order_by="created_at")


def get_videos(limit=None, offset=None, start=None, end=None, keys={}, has_route=False):
    where = []
    if start:
        where.append("created_at >= :start")
    if end:
        where.append("created_at <= :end")
    if has_route:
        where.append("route NOT NULL")
    # keys = {
    #   "tags": ["a", "b"],
    #   "playlists": ["a", "b"],
    # }
    for key, values in keys.items():
        where += [f"json_extract({key}, '$.{v}') = 1" for v in values]
    q = f"""
        SELECT * FROM videos WHERE
        {" AND ".join(where)}
        ORDER BY created_at DESC
    """

    if limit is not None:
        q += f" LIMIT {limit}"
    if offset is not None:
        q += f" OFFSET {offset}"

    return db.query(q, start=start, end=end)


def get_videos_bounds():
    q = """
        SELECT MIN(minx) as minx, MIN(miny) as miny,
            MAX(maxx) as maxx, MAX(maxy) as maxy
        FROM videos WHERE route IS NOT NULL
    """
    return next(db.query(q))


def get_distinct_keys(column):
    elts = db.query(f"SELECT DISTINCT(json_each.key) FROM videos, json_each({column})")
    return [t["key"] for t in elts]


def add_keys(column, videos_ids, keys):
    for _id in videos_ids:
        video = table.find_one(id=_id)
        if not video:
            continue
        video_elts = video[column] or {}
        table.update(
            # merge existing and new elements
            {"id": video["id"], column: {**video_elts, **keys}},
            ["id"],
        )


def remove_keys(column, videos_ids, keys):
    for _id in videos_ids:
        video = table.find_one(id=_id)
        if not video:
            continue
        for key in keys:
            q = f"""
                UPDATE videos
                SET {column} = json_remove({column}, '$.{key}')
                WHERE id = ?
            """
            db.query(q, video["id"])
