import dataset

from herotube import settings

DEFAULT_DSN = "sqlite:///videos.db"
db = dataset.connect(settings.get("database_url") or DEFAULT_DSN)
table = db["videos"]


def get_tags():
    tags = db.query("SELECT DISTINCT(json_each.key) FROM videos, json_each(tags)")
    return [t["key"] for t in tags]


def get_oldest_video():
    return table.find_one(order_by="created_at")


def get_videos(limit, offset, start=None, end=None, tags=[], has_route=False):
    where = []
    if start:
        where.append("created_at >= :start")
    if end:
        where.append("created_at <= :end")
    if has_route:
        where.append("route NOT NULL")
    where += [f"json_extract(tags, '$.{tag}') = 1" for tag in tags if tag]
    q = f"""
        SELECT * FROM videos WHERE
        {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT {limit}
        OFFSET {offset}
    """

    return db.query(q, start=start, end=end)


def get_videos_bounds():
    q = """
        SELECT MIN(minx) as minx, MIN(miny) as miny,
            MAX(maxx) as maxx, MAX(maxy) as maxy
        FROM videos WHERE route IS NOT NULL
    """
    return next(db.query(q))


def add_tags(videos_ids, tags):
    for _id in videos_ids:
        video = table.find_one(id=_id)
        if not video:
            continue
        video_tags = video["tags"] or {}
        table.update(
            # merge existing and new tags
            {"id": video["id"], "tags": {**video_tags, **tags}},
            ["id"],
        )


def remove_tags(videos_ids, tags):
    for _id in videos_ids:
        video = table.find_one(id=_id)
        if not video:
            continue
        for tag in tags:
            q = f"""
                UPDATE videos
                SET tags = json_remove(tags, '$.{tag}')
                WHERE id = {video['id']}
            """
            db.query(q)
