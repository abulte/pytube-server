
# 1 Mo
CHUNK_SIZE = 1000000


def get_chunk(path, byte1=None, byte2=None):
    file_size = path.stat().st_size
    start = 0

    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        # chunk size here
        length = start + CHUNK_SIZE
        if start + length > file_size:
            length = file_size - start

    with open(path, "rb") as f:
        f.seek(start)
        chunk = f.read(length)

    return chunk, start, length, file_size
