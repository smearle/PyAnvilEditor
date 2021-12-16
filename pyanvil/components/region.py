from io import FileIO
from pathlib import Path
from typing import Union
from . import Chunk
from .constants import Sizes


class Region:
    def __init__(self, region_file: Union[str, Path]):
        self.file_path = region_file
        self.timestamps: list[int] = []
        self.chunk_locations = []
        self.file: FileIO = None

        # locations and timestamps are parallel lists.
        # Indexes in one can be accessed in the other as well.
        self.chunk_locations: list[list[int]] = []
        self.timestamps: list[int] = []

    def __enter__(self) -> 'Region':
        self.__load_from_file()
        return self

    def __load_from_file(self):
        if not self.file:
            self.file = open(self.file_path, mode='rb')
        # 8KiB header. 4KiB chunk location table, 4KiB timestamp table
        region_header = self.file.read(1024 * (4 + 4))

        self.chunk_locations = []
        for (*offset, size) in Region.iterate_in_groups(region_header, group_size=4, start=0, end=4 * 1024):
            self.chunk_locations.append([
                int.from_bytes(offset, byteorder='big', signed=False) * Sizes.CHUNK_SECTOR_SIZE,
                size * Sizes.CHUNK_SECTOR_SIZE
            ])

        self.timestamps = [
            int.from_bytes(t, byteorder='big', signed=False)
            for t in Region.iterate_in_groups(
                region_header, group_size=4, start=4 * 1024, end=8 * 1024
            )
        ]

    def __exit__(self, exc_type, exc_value, traceback):
        if self.file:
            self.file.close()

    @ staticmethod
    def iterate_in_groups(container, group_size, start, end):
        return (container[i: (i + group_size)] for i in range(start, end, group_size))
