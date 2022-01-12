from flask import Blueprint, url_for

from herotube import db

blueprint = Blueprint("api", __name__, url_prefix="/api")


@blueprint.route("/videos/bounds")
def videos_bounds():
    videos = db.table.find(route={"not": None})
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "video-id": v["id"],
                "video-slug": v["title"],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [v["minx"], v["miny"]],
                    [v["minx"], v["maxy"]],
                    [v["maxx"], v["maxy"]],
                    [v["maxx"], v["miny"]],
                    [v["minx"], v["miny"]],
                ]]
            }
        } for v in videos]
    }


@blueprint.route("/videos/centers")
def videos_centers():
    videos = db.table.find(route={"not": None})
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "id": v["id"],
                "slug": v["title"],
                "thumbnail": url_for("media.static", filename=v["thumbnail"]),
                "link": url_for("video", rel_path=v["path"]),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    (v["maxx"] + v["minx"]) / 2,
                    (v["maxy"] + v["miny"]) / 2,
                ]
            }
        } for v in videos]
    }
