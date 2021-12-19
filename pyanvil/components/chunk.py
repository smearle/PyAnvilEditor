from typing import BinaryIO
from ..coordinate import AbsoluteCoordinate, ChunkCoordinate

from .component_base import ComponentBase
from . import ChunkSection, Sizes, Block, Biome
from . import CompoundTag, ListTag
from ..utility.nbt import NBT
from ..stream import InputStream, OutputStream
import zlib


class Chunk(ComponentBase):
    def __init__(self, coord: ChunkCoordinate, sections: dict[int, ChunkSection], raw_nbt, orig_size, parent_region: 'Region' = None):
        super().__init__(parent=parent_region)
        self.coordinate = coord
        self.sections: dict[int, ChunkSection] = sections
        self.raw_nbt = raw_nbt
        self.biomes = [Biome.from_index(i) for i in self.raw_nbt.get('Level').get('Biomes').get()]
        self.orig_size = orig_size
        self.__index = Chunk.to_region_chunk_index(coord)
        for section in self.sections.values():
            section.set_parent(self)

    def set_parent_region(self, region: 'Region'):
        self._parent = region

    @staticmethod
    def from_file(file: BinaryIO, offset: int, sections: int, parent_region: 'Region' = None) -> 'Chunk':
        file.seek(offset)
        datalen = int.from_bytes(file.read(4), byteorder="big", signed=False)
        file.read(1)  # Compression scheme
        decompressed = zlib.decompress(file.read(datalen - 1))
        data = NBT.parse_nbt(InputStream(decompressed))
        root_tag = data.get("Level")
        x = root_tag.get("xPos").get()
        z = root_tag.get("zPos").get()
        return Chunk(ChunkCoordinate(x, z), Chunk.__unpack_sections(data), data, datalen, parent_region=parent_region)

    def package_and_compress(self):
        """Serialize and compress chunk to raw data"""
        stream = OutputStream()
        # Serialize and compress chunk
        chunkNBT = self.pack()
        chunkNBT.serialize(stream)
        return zlib.compress(stream.get_data())

    @property
    def index(self):
        return self.__index

    @staticmethod
    def to_region_chunk_index(coord: ChunkCoordinate):
        return (coord.x % Sizes.REGION_WIDTH) + (coord.z % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH

    def get_block(self, block_pos: AbsoluteCoordinate):
        coords = [block_pos.x, block_pos.y, block_pos.z]
        return self.get_section(block_pos.y).get_block(
            [
                n % Sizes.SUBCHUNK_WIDTH for n in coords
            ]
        )

    def get_section(self, y) -> ChunkSection:
        key = int(y / Sizes.SUBCHUNK_WIDTH)
        if key not in self.sections:
            self.sections[key] = ChunkSection(
                CompoundTag(),
                key,
                blocks=[Block(dirty=True) for i in range(4096)],
                parent_chunk=self
            )
        return self.sections[key]

    def find_like(self, string) -> list[Block]:
        results = []
        for sec in self.sections:
            section = self.sections[sec]
            for x1 in range(Sizes.SUBCHUNK_WIDTH):
                for y1 in range(Sizes.SUBCHUNK_WIDTH):
                    for z1 in range(Sizes.SUBCHUNK_WIDTH):
                        if string in section.get_block((x1, y1, z1))._state.name:
                            results.append(
                                (
                                    (
                                        x1 + self.coordinate.x * Sizes.SUBCHUNK_WIDTH,
                                        y1 + sec * Sizes.SUBCHUNK_WIDTH,
                                        z1 + self.coordinate.z * Sizes.SUBCHUNK_WIDTH,
                                    ),
                                    section.get_block((x1, y1, z1)),
                                )
                            )
        return results

    # Blockstates are packed based on the number of values in the pallet.
    # This selects the pack size, then splits out the ids
    @staticmethod
    def __unpack_sections(raw_nbt):
        sections = {}
        for section in raw_nbt.get('Level').get('Sections').children:
            sections[section.get('Y').get()] = ChunkSection.from_nbt(section)
        return sections

    def pack(self):
        new_sections: ListTag = ListTag(
            CompoundTag.clazz_id,
            tag_name='Sections',
            children=[sec.serialize() for sec in self.sections.values()]
        )
        new_nbt = self.raw_nbt.clone()
        new_nbt.get('Level').add_child(new_sections)

        return new_nbt

    def __str__(self):
        return f'Chunk({str(self.coordinate.x)},{str(self.coordinate.z)})'
