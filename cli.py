from pathlib import Path

import ffpb

from minicli import cli, run

import settings

INPUT_PATH = Path(settings.get("VIDEOS_PATH"))
OUTPUT_PATH = Path(settings.get("OUTPUT_PATH", "./output"))


@cli(name="import")
def do_import(crf="35", date="", force=False):
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
        print(tb_path)
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


@cli
def metadata(filepath):
    # path = Path(filepath)
    import ffmpeg
    videos = INPUT_PATH.glob("**/*.MP4")
    for v in videos:
        res = ffmpeg.probe(str(v))
        print(res['format']['tags']['creation_time'])


if __name__ == "__main__":
    run()
