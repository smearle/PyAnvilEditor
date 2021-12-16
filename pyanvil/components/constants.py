from enum import IntEnum


class Sizes(IntEnum):
    REGION_WIDTH = 32
    SUBCHUNK_WIDTH = 16,
    CHUNK_SECTOR_SIZE = 4096  # 4KiB
