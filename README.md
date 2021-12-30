# pytube-server

## Convert (GoPro) videos to web-playable format

`PYT_VIDEOS_PATH={src_folder} PYT_OUTPUT_PATH={dest_folder} python cli.py import`

## Run web app to serve converted files

`flask run`

## Fix creation data metadata on GoPro files

E.g., add one year, using [ExifTool](https://exiftool.org):

`exiftool "-CreateDate+=1:0:0 0:0:0" *.MP4`

## Ansible deploy

```
cd ansible
ansible-playbook site.yml
```

## See also

https://github.com/abulte/hero-plus-dl to download videos from GoPro Hero Plus Cloud.
