from io import FileIO
from pathlib import Path
from typing import Union
from . import Chunk
from .constants import Sizes


class Region:
    def __init__(self, region_file: Union[str, Path]):
        self.file_path = region_file
        self.file: FileIO = None
        self.chunks: dict[int, Chunk] = {}

        # locations and timestamps are parallel lists.
        # Indexes in one can be accessed in the other as well.
        self.__chunk_locations: list[list[int]] = None
        self.__timestamps: list[int] = None

        # Uninterpreted raw data
        self.__chunk_location_data: bytes = None
        self.__timestamps_data: bytes = None

    def __enter__(self) -> 'Region':
        self.__load_from_file()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.file:
            self.file.close()

    def __load_from_file(self):
        """Read header into buffer. Interpretation of header data happens upon first access."""
        self.__ensure_file_open()
        # 8KiB header. 4KiB chunk location table, 4KiB timestamp table
        self.__chunk_location_data = self.file.read(4 * 1024)
        self.__timestamps_data = self.file.read(4 * 1024)

    def __ensure_file_open(self):
        if not self.file:
            self.file = open(self.file_path, mode='rb')

    def get_chunk(self, x, z):
        chunk_index = Chunk.to_region_chunk_index(x, z)
        print(f'Loading {x}x {z}z from {self.file_path}')
        if not chunk_index in self.chunks:
            self.__ensure_file_open()
            offset, sections = self.chunk_locations[chunk_index]
            chunk = Chunk.from_file(file=self.file, offset=offset, sections=sections)
            self.chunks[chunk_index] = chunk
            return chunk
        else:
            return self.chunks[chunk_index]

    @property
    def chunk_locations(self) -> list[list[int]]:
        if self.__chunk_locations is None:
            # Interpret header chunk
            self.__chunk_locations = [
                # Nested list containing 2 elements
                [
                    int.from_bytes(offset, byteorder='big', signed=False) * Sizes.CHUNK_SECTOR_SIZE,
                    size * Sizes.CHUNK_SECTOR_SIZE
                ]
                for (*offset, size) in Region.iterate_in_groups(
                    self.__chunk_location_data, group_size=4, start=0, end=4 * 1024
                )
            ]
        return self.__chunk_locations

    @property
    def timestamps(self) -> list[list[int]]:
        if self.__timestamps is None:
            # Interpret header chunk
            self.__timestamps = [
                int.from_bytes(t, byteorder='big', signed=False)
                for t in Region.iterate_in_groups(
                    self.__timestamps_data, group_size=4, start=4 * 1024, end=8 * 1024
                )
            ]
        return self.__timestamps

    @ staticmethod
    def iterate_in_groups(container, group_size, start, end):
        return (container[i: (i + group_size)] for i in range(start, end, group_size))
