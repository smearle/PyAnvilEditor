from typing import BinaryIO
from . import ChunkSection, Sizes, Block, BlockState, Biome
from . import CompoundTag, ListTag
from ..utility.nbt import NBT
from ..stream import InputStream, OutputStream
import zlib
import math


class Chunk:
    def __init__(self, xpos, zpos, sections: dict[int, ChunkSection], raw_nbt, orig_size):
        self.xpos = xpos
        self.zpos = zpos
        self.sections: dict[int, ChunkSection] = sections
        self.raw_nbt = raw_nbt
        self.biomes = [Biome.from_index(i) for i in self.raw_nbt.get('Level').get('Biomes').get()]
        self.orig_size = orig_size
        self.__index = Chunk.to_region_chunk_index(xpos, zpos)

    @staticmethod
    def from_file(file: BinaryIO, offset: int, sections: int) -> 'Chunk':
        file.seek(offset)
        datalen = int.from_bytes(file.read(4), byteorder="big", signed=False)
        file.read(1)  # Compression scheme
        decompressed = zlib.decompress(file.read(datalen - 1))
        data = NBT.parse_nbt(InputStream(decompressed))
        root_tag = data.get("Level")
        x = root_tag.get("xPos").get()
        z = root_tag.get("zPos").get()
        return Chunk(x, z, Chunk.unpack(data), data, datalen)

    @property
    def index(self):
        return self.__index

    @staticmethod
    def to_region_chunk_index(x, z):
        return (x % Sizes.REGION_WIDTH) + (z % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH

    def get_block(self, block_pos):
        return self.get_section(block_pos[1]).get_block(
            [
                n % Sizes.SUBCHUNK_WIDTH for n in block_pos
            ]
        )

    def get_section(self, y) -> ChunkSection:
        key = int(y / Sizes.SUBCHUNK_WIDTH)
        if key not in self.sections:
            self.sections[key] = ChunkSection(
                [Block(dirty=True) for i in range(4096)],
                CompoundTag(),
                key
            )
        return self.sections[key]

    def find_like(self, string):
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
                                        x1 + self.xpos * Sizes.SUBCHUNK_WIDTH,
                                        y1 + sec * Sizes.SUBCHUNK_WIDTH,
                                        z1 + self.zpos * Sizes.SUBCHUNK_WIDTH,
                                    ),
                                    section.get_block((x1, y1, z1)),
                                )
                            )
        return results

    # Blockstates are packed based on the number of values in the pallet.
    # This selects the pack size, then splits out the ids
    @staticmethod
    def unpack(raw_nbt):
        sections = {}
        for section in raw_nbt.get('Level').get('Sections').children:
            sections[section.get('Y').get()] = ChunkSection.from_nbt(section)
        return sections

    def pack(self):
        new_sections = ListTag(
            CompoundTag.clazz_id,
            tag_name='Sections',
            children=[self.sections[sec].serialize() for sec in self.sections]
        )
        new_nbt = self.raw_nbt.clone()
        new_nbt.get('Level').add_child(new_sections)

        return new_nbt

    def __str__(self):
        return f'Chunk({str(self.xpos)},{str(self.zpos)})'
