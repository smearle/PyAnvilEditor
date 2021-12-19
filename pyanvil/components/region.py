import math
import sys
from io import FileIO
from pathlib import Path
from time import time
from typing import BinaryIO, Union
import logging

from ..coordinate import ChunkCoordinate
from . import Chunk
from .component_base import ComponentBase
from .constants import Sizes


class Region(ComponentBase):
    def __init__(self, region_file: Union[str, Path]):
        super().__init__(parent=None)
        self.file_path = region_file
        self.file: FileIO = None
        self.chunks: dict[int, Chunk] = {}

        # locations and timestamps are parallel lists.
        # Indexes in one can be accessed in the other as well.
        self.__chunk_locations: list[list[int]] = None
        self.__timestamps: list[int] = None

        # Uninterpreted raw data
        # Header
        self.__chunk_location_data: bytes = None
        self.__timestamps_data: bytes = None
        # Uninterpreted chunks mapped to their index
        self.__raw_chunk_data: dict[int, bytes] = {}

        self.__load_from_file()

    def __enter__(self) -> 'Region':
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.is_dirty:
            self.save()
        if self.file:
            self.file.close()

    def __load_from_file(self):
        self.__ensure_file_open()
        # 8KiB header. 4KiB chunk location table, 4KiB timestamp table
        self.__chunk_location_data = self.file.read(4 * 1024)
        self.__timestamps_data = self.file.read(4 * 1024)
        self.__read_chunks_to_memory()

    def __ensure_file_open(self):
        if not self.file:
            self.file = open(self.file_path, mode='r+b')

    def __read_chunks_to_memory(self):
        for offset, size in self.chunk_locations:
            self.file.seek(offset)
            self.__raw_chunk_data[offset] = self.file.read(size)

    def save(self):
        self.__ensure_file_open()
        self.file.seek((4 + 4) * 1024)  # Skip to the end of the region header
        # Sort chunks by offset
        #self.chunks.sort(key=lambda chunk: self.__chunk_locations[chunk.index][0])

        rest_of_the_data = self.__read_region_after_header()

        for index, chunk in self.chunks.items():
            self.timestamps[index] = int(time())

            chunk_data: bytes = chunk.package_and_compress()

            datalen = len(chunk_data)
            block_data_len = math.ceil((datalen + 5) / 4096.0) * 4096

            # Constuct new data block
            data: bytes = (datalen + 1).to_bytes(length=4, byteorder='big', signed=False)  # Total length of chunk data
            data += (2).to_bytes(length=1, byteorder='big', signed=False)
            data += chunk_data
            data += (0).to_bytes(block_data_len - (datalen + 5), byteorder='big', signed=False)

            loc = self.__chunk_locations[index]
            original_sector_length = loc[1]
            data_len_diff = block_data_len - original_sector_length
            if data_len_diff != 0 and self.debug:
                print(f'Danger: Diff is {data_len_diff}, shifting required!')

            self.__chunk_locations[index][1] = block_data_len

            if loc[0] == 0 or loc[1] == 0:
                print('Chunk not generated', chunk)
                sys.exit(0)

            # Adjust sectors after this one that need their locations recalculated
            for i, other_loc in enumerate(self.__chunk_locations):
                if other_loc[0] > loc[0]:
                    self.__chunk_locations[i][0] = other_loc[0] + data_len_diff

            header_length = 2 * 4096
            rest_of_the_data[(loc[0] - header_length):(loc[0] + original_sector_length - header_length)] = data
            logging.debug(f'Saving {chunk} with', {'loc': loc, 'new_len': datalen, 'old_len': chunk.orig_size, 'sector_len': block_data_len})

        # rewrite entire file with new chunks and locations recorded
        self.file.seek(0)
        self.__write_header(self.file)

        self.file.write(rest_of_the_data)

        required_padding = (math.ceil(self.file.tell() / 4096.0) * 4096) - self.file.tell()

        self.file.write((0).to_bytes(required_padding, byteorder='big', signed=False))

        self._is_dirty = False

    def __write_header(self, file: BinaryIO):
        for c_loc in self.__chunk_locations:
            file.write(int(c_loc[0] / 4096).to_bytes(3, byteorder='big', signed=False))
            file.write(int(c_loc[1] / 4096).to_bytes(1, byteorder='big', signed=False))

        for ts in self.timestamps:
            file.write(ts.to_bytes(4, byteorder='big', signed=False))

    def get_chunk(self, coord: ChunkCoordinate):
        chunk_index = Chunk.to_region_chunk_index(coord)
        print(f'Loading {coord.x}x {coord.z}z from {self.file_path}')
        if not chunk_index in self.chunks:
            self.__ensure_file_open()
            offset, sections = self.chunk_locations[chunk_index]
            chunk = Chunk.from_file(file=self.file, offset=offset, sections=sections, parent_region=self)
            self.chunks[chunk_index] = chunk
            return chunk
        else:
            return self.chunks[chunk_index]

    def __read_region_after_header(self):
        self.__ensure_file_open()
        self.file.seek((4 + 4) * 1024)
        return bytearray(self.file.read())

    @property
    def chunk_locations(self) -> list[list[int]]:
        if self.__chunk_locations is None:
            # Interpret header chunk
            self.__chunk_locations = [
                # Nested list containing 2 elements, one taking 3 bytes, one with 1 byte
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

    @staticmethod
    def iterate_in_groups(container, group_size, start, end):
        return (container[i: (i + group_size)] for i in range(start, end, group_size))
