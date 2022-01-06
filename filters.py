import json

from datetime import datetime

import humanize

from app import app


@app.template_filter()
def datetimeformat(value):
    if not value:
        return
    value = datetime.fromisoformat(value)
    date_fmt = "%Y-%m-%d %H:%M:%S"
    return f"{humanize.naturaltime(value)} — {value.strftime(date_fmt)}"


@app.template_filter()
def durationformat(value):
    if not value:
        return
    return humanize.precisedelta(float(value))


@app.template_filter()
def fromjson(value):
    if not value:
        return
    return json.loads(value)
