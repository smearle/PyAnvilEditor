from io import FileIO
import sys
import math
import zlib
import time
from pathlib import Path

from pyanvil.components.region import Region
from .utility.nbt import NBT
from .stream import InputStream, OutputStream
from .canvas import Canvas
from .components import Sizes, Chunk


class World:
    def __init__(self, world_folder, save_location=None, debug=False, read=True, write=True):
        self.debug = debug
        if save_location is not None:
            self.world_folder = Path(save_location) / world_folder
        else:
            self.world_folder = Path(world_folder)
        if not self.world_folder.is_dir():
            raise FileNotFoundError(f'No such folder \"{self.world_folder}\"')
        self.chunks = {}

    def __enter__(self) -> 'World':
        return self

    def __exit__(self, typ, val, trace):
        if typ is None:
            self.close()

    def flush(self):
        self.close()
        self.chunks: dict[int, Chunk] = {}

    def close(self):
        chunks_by_region: dict[str, list[Chunk]] = {}
        for chunk_pos, chunk in self.chunks.items():
            region = self._get_region_file_name(chunk_pos)
            if region not in chunks_by_region:
                chunks_by_region[region] = []
            chunks_by_region[region].append(chunk)

        for region_name, chunks in chunks_by_region.items():
            with open(self.world_folder / 'region' / region_name, mode='r+b') as region:
                region.seek(0)
                locations = [
                    [
                        int.from_bytes(region.read(3), byteorder='big', signed=False) * 4096,
                        int.from_bytes(region.read(1), byteorder='big', signed=False) * 4096
                    ]
                    for i in range(1024)
                ]

                timestamps = [int.from_bytes(region.read(4), byteorder='big', signed=False) for i in range(1024)]

                data_in_file = bytearray(region.read())

                chunks.sort(key=lambda chunk: locations[chunk.get_index()][0])
                # print("writing chunks", [str(c) + ":" + str(locations[((chunk.xpos % Sizes.REGION_WIDTH) + (chunk.zpos % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH)][0]) for c in chunks])

                for chunk in chunks:
                    chunk_index = chunk.get_index()
                    strm = OutputStream()
                    timestamps[chunk_index] = int(time.time())

                    chunkNBT = chunk.pack()
                    chunkNBT.serialize(strm)
                    data = zlib.compress(strm.get_data())
                    datalen = len(data)
                    block_data_len = math.ceil((datalen + 5) / 4096.0) * 4096

                    # Constuct new data block
                    data = (datalen + 1).to_bytes(4, byteorder='big', signed=False) + \
                        (2).to_bytes(length=1, byteorder='big', signed=False) + \
                        data + \
                        (0).to_bytes(block_data_len - (datalen + 5), byteorder='big', signed=False)

                    loc = locations[chunk_index]
                    original_sector_length = loc[1]
                    data_len_diff = block_data_len - original_sector_length
                    if data_len_diff != 0 and self.debug:
                        print(f'Danger: Diff is {data_len_diff}, shifting required!')

                    locations[chunk_index][1] = block_data_len

                    if loc[0] == 0 or loc[1] == 0:
                        print('Chunk not generated', chunk)
                        sys.exit(0)

                    # Adjust sectors after this one that need their locations recalculated
                    for i, other_loc in enumerate(locations):
                        if other_loc[0] > loc[0]:
                            locations[i][0] = other_loc[0] + data_len_diff

                    header_length = 2 * 4096
                    data_in_file[(loc[0] - header_length):(loc[0] + original_sector_length - header_length)] = data
                    if self.debug:
                        print(f'Saving {chunk} with', {'loc': loc, 'new_len': datalen, 'old_len': chunk.orig_size, 'sector_len': block_data_len})

                # rewrite entire file with new chunks and locations recorded
                region.seek(0)

                for c_loc in locations:
                    region.write(int(c_loc[0] / 4096).to_bytes(3, byteorder='big', signed=False))
                    region.write(int(c_loc[1] / 4096).to_bytes(1, byteorder='big', signed=False))

                for ts in timestamps:
                    region.write(ts.to_bytes(4, byteorder='big', signed=False))

                region.write(data_in_file)

                required_padding = (math.ceil(region.tell() / 4096.0) * 4096) - region.tell()

                region.write((0).to_bytes(required_padding, byteorder='big', signed=False))

    def get_block(self, block_pos):
        chunk_pos = self._to_chunk_coordinates(block_pos)
        chunk = self.get_chunk(chunk_pos)
        return chunk.get_block(block_pos)

    def get_chunk(self, chunk_pos) -> Chunk:
        if chunk_pos not in self.chunks:
            self._load_chunk(chunk_pos)

        return self.chunks[chunk_pos]

    def get_canvas(self):
        return Canvas(self)

    def _load_chunk(self, chunk_pos):
        file_name = self._get_region_file_name(chunk_pos)
        with Region(self.world_folder / 'region' / file_name) as region:
            loc = region.chunk_locations[((chunk_pos[0] % Sizes.REGION_WIDTH) + (chunk_pos[1] % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH)]
            if self.debug:
                print('Loading', chunk_pos, 'from', file_name)
            chunk = World._load_binary_chunk_at(region, offset=loc[0], max_size=loc[1])
            self.chunks[chunk_pos] = chunk

    @staticmethod
    def _load_binary_chunk_at(region_file: FileIO, offset, max_size) -> Chunk:
        region_file.seek(offset)
        datalen = int.from_bytes(region_file.read(4), byteorder='big', signed=False)
        region_file.read(1)  # Compression scheme
        decompressed = zlib.decompress(region_file.read(datalen - 1))
        data = NBT.parse_nbt(InputStream(decompressed))
        chunk_pos = (data.get('Level').get('xPos').get(), data.get('Level').get('zPos').get())
        chunk = Chunk(
            chunk_pos[0],
            chunk_pos[1],
            Chunk.unpack(data),
            data,
            datalen
        )
        return chunk

    def _get_region_file_name(self, chunk_pos):
        return 'r.' + '.'.join([str(x) for x in self._get_region(chunk_pos)]) + '.mca'

    def _to_chunk_coordinates(self, block_pos: tuple[int, int, int]) -> tuple[int, int]:
        return (block_pos[0] // Sizes.SUBCHUNK_WIDTH, block_pos[2] // Sizes.SUBCHUNK_WIDTH)

    def _get_region(self, chunk_pos: tuple[int, int]):
        return (chunk_pos[0] // Sizes.REGION_WIDTH, chunk_pos[1] // Sizes.REGION_WIDTH)
