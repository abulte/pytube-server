from datetime import datetime
from pathlib import Path

import contextily
import ffmpeg
import ffpb
import gpmf

from dotenv import load_dotenv
from minicli import cli, run

import settings
import db

load_dotenv()

INPUT_PATH = Path(settings.get("VIDEOS_PATH"))
OUTPUT_PATH = Path(settings.get("OUTPUT_PATH", "./output"))
DATE_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


@cli(name="import")
def do_import(crf="35", date="", force=False):
    """
    Convert videos in `PYT_VIDEOS_PATH` to compressed videos in
    `PYT_OUTPUT_PATH`. It will also:
        - extract a thumbnail
        - extract a route (GPX) image if available
        - populate a database with metadatas

    :crf: compression factor
    :date: process only for this date (tree folder based)
    :force: force processing even if output files already exist
    """
    videos = INPUT_PATH.glob("**/*.MP4")
    for v in videos:
        rel = v.relative_to(INPUT_PATH)
        # get rid of the useless GoPro stuff and keep date and file
        out = OUTPUT_PATH / rel.parts[0] / rel.parts[-1].lower()
        if date and rel.parts[0] != date:
            print(f"{out} not matching date")
            continue

        if not out.exists() or force:
            print(v, out)
            out.parent.mkdir(parents=True, exist_ok=True)
            argv = [
                "-i", str(v),
                "-movflags", "+faststart",
                "-vcodec", "libx264",
                "-acodec", "aac",
                "-map_metadata:g", "0:g",
                # 35 : 271Mo / 1,23Go
                # 28 : 827Mo / 1,23Go
                "-crf", crf,
                "-y",
                str(out)
            ]
            print(' '.join(argv))
            ffpb.main(argv=argv)
        else:
            print(f"{out} already exists, skipping")

        # make thumbnail
        tb_path = out.with_suffix('.jpg')
        if not tb_path.exists() or force:
            argv = [
                "-ss", "1",
                "-i", str(out),
                "-vframes", "1",
                # 16:9
                "-s", "854x480",
                "-f", "image2",
                "-y",
                str(tb_path)
            ]
            ffpb.main(argv=argv)

        # extract gpx image
        route_path = out.with_suffix('.route.png')
        if not route_path.exists() or force:
            stream = gpmf.io.extract_gpmf_stream(str(v))
            try:
                gpmf.gps_plot.plot_gps_trace_from_stream(
                    stream,
                    map_provider=contextily.providers.OpenTopoMap,
                    output_path=str(route_path),
                )
            except Exception as e:
                print(f"[ERROR] generating route: {e}")

        # register to DB
        metadata = ffmpeg.probe(str(v))
        fm_meta = metadata.get("format")
        if not fm_meta or not fm_meta.get("tags"):
            print(f"[ERROR] wrong metadata: {metadata}")
            continue
        creation_date = fm_meta["tags"]["creation_time"]
        route = str(route_path.relative_to(OUTPUT_PATH)) \
            if route_path.exists() else None
        db.table.upsert({
            "path": str(out.relative_to(OUTPUT_PATH)),
            "original_path": str(v),
            "thumbnail": str(tb_path.relative_to(OUTPUT_PATH)),
            "route": route,
            "created_at": datetime.strptime(creation_date, DATE_FMT),
            "duration": float(fm_meta["duration"]),
            "metadata": fm_meta,
            "title": out.stem,
        }, ["path"])


@cli
def migrate():
    """Poor man's migration"""
    if not db.table.has_column("tags"):
        db.table.create_column("tags", db.db.types.Types().json)
    print("Migrated.")


if __name__ == "__main__":
    print(f"""
 _ __  _  _  _          _
| '_ \| || || |_  _  _ | |__  ___
| .__/ \_. ||  _|| || ||  _ \/ -_)
|_|    |__/  \__| \_._||____/\___|

Input   : {INPUT_PATH.resolve()}
Output  : {OUTPUT_PATH.resolve()}

""")  # noqa
    run()
