import sys
import math
import zlib
import time
from enum import Enum
from pathlib import Path
from .nbt import NBT
from .stream import InputStream, OutputStream
from .biomes import Biome
from .canvas import Canvas


class Sizes(Enum):
    REGION_WIDTH = 32
    CHUNK_WIDTH = 16


class BlockState:
    def __init__(self, name: str = 'minecraft:air', props: map = {}):
        self.name = name
        self.props = props
        self.id = None

    def __str__(self):
        return f'BlockState({self.name}, {str(self.props)})'

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name and self.props == other.props

    def clone(self):
        return BlockState(self.name, self.props.copy())


class Block:
    def __init__(self, state=BlockState(), block_light: int = 0, sky_light: int = 0, dirty: bool = False):
        self._state: BlockState = state
        self.block_light: int = block_light
        self.sky_light: int = sky_light
        self._dirty: bool = dirty

    def __str__(self):
        return f'Block({str(self._state)}, {self.block_light}, {self.sky_light})'

    def set_state(self, state):
        self._dirty = True
        if type(state) is BlockState:
            self._state = state
        else:
            self._state = BlockState(state, {})

    def get_state(self):
        return self._state.clone()


class ChunkSection:
    def __init__(self, blocks, raw_section, y_index):
        self.blocks = blocks
        self.raw_section = raw_section
        self.y_index = y_index

    def get_block(self, block_pos):
        x = block_pos[0]
        y = block_pos[1]
        z = block_pos[2]

        return self.blocks[x + z * Sizes.CHUNK_WIDTH + y * Sizes.CHUNK_WIDTH ** 2]

    def serialize(self):
        serial_section = self.raw_section
        dirty = any([b._dirty for b in self.blocks])
        if dirty:
            self.palette = list(set([b._state for b in self.blocks] + [BlockState('minecraft:air', {})]))
            self.palette.sort(key=lambda s: s.name)
            serial_section.add_child(NBT.ByteTag(self.y_index, tag_name='Y'))
            mat_id_mapping = {self.palette[i]: i for i in range(len(self.palette))}
            new_palette = self._serialize_palette()
            serial_section.add_child(new_palette)
            serial_section.add_child(self._serialize_blockstates(mat_id_mapping))

        if not serial_section.has('SkyLight'):
            serial_section.add_child(NBT.ByteArrayTag(tag_name='SkyLight', children=[NBT.ByteTag(-1, tag_name='None') for i in range(2048)]))

        if not serial_section.has('BlockLight'):
            serial_section.add_child(NBT.ByteArrayTag(tag_name='BlockLight', children=[NBT.ByteTag(-1, tag_name='None') for i in range(2048)]))

        return serial_section

    def _serialize_palette(self):
        serial_palette = NBT.ListTag(NBT.CompoundTag.clazz_id, tag_name='Palette')
        for state in self.palette:
            palette_item = NBT.CompoundTag(tag_name='None', children=[
                NBT.StringTag(state.name, tag_name='Name')
            ])
            if len(state.props) != 0:
                serial_props = NBT.CompoundTag(tag_name='Properties')
                for name, val in state.props.items():
                    serial_props.add_child(NBT.StringTag(str(val), tag_name=name))
                palette_item.add_child(serial_props)
            serial_palette.add_child(palette_item)

        return serial_palette

    def _serialize_blockstates(self, state_mapping):
        serial_states = NBT.LongArrayTag(tag_name='BlockStates')
        width = math.ceil(math.log(len(self.palette), 2))
        if width < 4:
            width = 4

        # max amount of states that fit in a long
        states_per_long = 64 // width

        # amount of longs
        arraylength = math.ceil(len(self.blocks) / states_per_long)

        for long_index in range(arraylength):
            lng = 0
            for state in range(states_per_long):
                # insert blocks in reverse, so first one ends up most to the right
                block_index = long_index*states_per_long + (states_per_long - state - 1)

                if block_index < len(self.blocks):
                    block = self.blocks[block_index]
                    lng = (lng << width) + state_mapping[block._state]

            lng = int.from_bytes(lng.to_bytes(8, byteorder='big', signed=False), byteorder='big', signed=True)
            serial_states.add_child(NBT.LongTag(lng))
        return serial_states


class Chunk:
    def __init__(self, xpos, zpos, sections, raw_nbt, orig_size):
        self.xpos = xpos
        self.zpos = zpos
        self.sections = sections
        self.raw_nbt = raw_nbt
        self.biomes = [Biome.from_index(i) for i in self.raw_nbt.get('Level').get('Biomes').get()]
        self.orig_size = orig_size

    def get_block(self, block_pos):
        return self.get_section(block_pos[1]).get_block([n % Sizes.CHUNK_WIDTH for n in block_pos])

    def get_section(self, y):
        key = int(y / Sizes.CHUNK_WIDTH)
        if key not in self.sections:
            self.sections[key] = ChunkSection(
                [Block(dirty=True) for i in range(4096)],
                NBT.CompoundTag(),
                key
            )
        return self.sections[key]

    def find_like(self, string):
        results = []
        for sec in self.sections:
            section = self.sections[sec]
            for x1 in range(Sizes.CHUNK_WIDTH):
                for y1 in range(Sizes.CHUNK_WIDTH):
                    for z1 in range(Sizes.CHUNK_WIDTH):
                        if string in section.get_block((x1, y1, z1))._state.name:
                            results.append((
                                (x1 + self.xpos * Sizes.CHUNK_WIDTH, y1 + sec * Sizes.CHUNK_WIDTH, z1 + self.zpos * Sizes.CHUNK_WIDTH),
                                section.get_block((x1, y1, z1))
                            ))
        return results

    # Blockstates are packed based on the number of values in the pallet.
    # This selects the pack size, then splits out the ids
    def unpack(raw_nbt):
        sections = {}
        for section in raw_nbt.get('Level').get('Sections').children:
            states = []  # Sections which contain only air have no states.
            if section.has('BlockStates'):
                flatstates = [c.get() for c in section.get('BlockStates').children]
                pack_size = int((len(flatstates) * 64) / (Sizes.CHUNK_WIDTH ** 3))
                states = [
                    Chunk._read_width_from_loc(flatstates, pack_size, i) for i in range(Sizes.CHUNK_WIDTH ** 3)
                ]
            palette: list[BlockState] = None
            if section.has('Palette'):
                palette = [
                    BlockState(
                        state.get('Name').get(),
                        state.get('Properties').to_dict() if state.has('Properties') else {}
                    ) for state in section.get('Palette').children
                ]
            block_lights = Chunk._divide_nibbles(section.get('BlockLight').get()) if section.has('BlockLight') else None
            sky_lights = Chunk._divide_nibbles(section.get('SkyLight').get()) if section.has('SkyLight') else None
            blocks = []
            for i, state in enumerate(states):
                state = palette[state]
                block_light = block_lights[i] if block_lights else 0
                sky_light = sky_lights[i] if sky_lights else 0
                blocks.append(Block(state=state, block_light=block_light, sky_light=sky_light))
            sections[section.get('Y').get()] = ChunkSection(blocks, section, section.get('Y').get())
        return sections

    def _divide_nibbles(arry):
        rtn = []
        f2_mask = (2 ** 4) - 1
        f1_mask = f2_mask << 4
        for s in arry:
            rtn.append(s & f1_mask)
            rtn.append(s & f2_mask)

        return rtn

    def pack(self):
        new_sections = NBT.ListTag(NBT.CompoundTag.clazz_id, tag_name='Sections', children=[
            self.sections[sec].serialize() for sec in self.sections
        ])
        new_nbt = self.raw_nbt.clone()
        new_nbt.get('Level').add_child(new_sections)

        return new_nbt

    def _read_width_from_loc(long_list, width, position):
        # max amount of blockstates that fit in each long
        states_per_long = 64 // width

        # the long in which this blockstate is stored
        long_index = position // states_per_long

        # at which bit in the long this state is located
        position_in_long = (position % states_per_long)*width
        return Chunk._read_bits(long_list[long_index], width, position_in_long)

    def _read_bits(num, width: int, start: int):
        # create a mask of size 'width' of 1 bits
        mask = (2 ** width) - 1
        # shift it out to where we need for the mask
        mask = mask << start
        # select the bits we need
        comp = num & mask
        # move them back to where they should be
        comp = comp >> start

        return comp

    def __str__(self):
        return f'Chunk({str(self.xpos)},{str(self.zpos)})'


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

    def __enter__(self):
        return self

    def __exit__(self, typ, val, trace):
        if typ is None:
            self.close()

    def flush(self):
        self.close()
        self.chunks = {}

    def close(self):
        chunks_by_region = {}
        for chunk_pos, chunk in self.chunks.items():
            region = self._get_region_file(chunk_pos)
            if region not in chunks_by_region:
                chunks_by_region[region] = []
            chunks_by_region[region].append(chunk)

        for region_name, chunks in chunks_by_region.items():
            with open(self.world_folder / 'region' / region_name, mode='r+b') as region:
                region.seek(0)
                locations = [[
                    int.from_bytes(region.read(3), byteorder='big', signed=False) * 4096,
                    int.from_bytes(region.read(1), byteorder='big', signed=False) * 4096
                ] for i in range(1024)]

                timestamps = [int.from_bytes(region.read(4), byteorder='big', signed=False) for i in range(1024)]

                data_in_file = bytearray(region.read())

                chunks.sort(key=lambda chunk: locations[((chunk.xpos % Sizes.REGION_WIDTH) + (chunk.zpos % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH)][0])
                # print("writing chunks", [str(c) + ":" + str(locations[((chunk.xpos % Sizes.REGION_WIDTH) + (chunk.zpos % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH)][0]) for c in chunks])

                for chunk in chunks:
                    strm = OutputStream()
                    chunkNBT = chunk.pack()
                    chunkNBT.serialize(strm)
                    data = zlib.compress(strm.get_data())
                    datalen = len(data)
                    block_data_len = math.ceil((datalen + 5) / 4096.0) * 4096
                    chunk_index = (chunk.xpos % Sizes.REGION_WIDTH) + (chunk.zpos % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH
                    # Constuct new data block
                    data = (datalen + 1).to_bytes(4, byteorder='big', signed=False) + \
                        (2).to_bytes(length=1, byteorder='big', signed=False) + \
                        data + \
                        (0).to_bytes(block_data_len - (datalen + 5), byteorder='big', signed=False)

                    timestamps[chunk_index] = int(time.time())

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

                    header_length = 2*4096
                    data_in_file[(loc[0] - header_length):(loc[0] + original_sector_length - header_length)] = data
                    if self.debug:
                        print(f'Saving {chunk} with', {'loc': loc, 'new_len': datalen, 'old_len': chunk.orig_size, 'sector_len': block_data_len})

                # rewrite entire file with new chunks and locations recorded
                region.seek(0)

                for c_loc in locations:
                    region.write(int(c_loc[0]/4096).to_bytes(3, byteorder='big', signed=False))
                    region.write(int(c_loc[1]/4096).to_bytes(1, byteorder='big', signed=False))

                for ts in timestamps:
                    region.write(ts.to_bytes(4, byteorder='big', signed=False))

                region.write(data_in_file)

                required_padding = (math.ceil(region.tell()/4096.0) * 4096) - region.tell()

                region.write((0).to_bytes(required_padding, byteorder='big', signed=False))

    def get_block(self, block_pos):
        chunk_pos = self._get_chunk(block_pos)
        chunk = self.get_chunk(chunk_pos)
        return chunk.get_block(block_pos)

    def get_chunk(self, chunk_pos):
        if chunk_pos not in self.chunks:
            self._load_chunk(chunk_pos)

        return self.chunks[chunk_pos]

    def get_canvas(self):
        return Canvas(self)

    def _load_chunk(self, chunk_pos):
        with open(self.world_folder / 'region' / self._get_region_file(chunk_pos), mode='rb') as region:
            locations = [[
                int.from_bytes(region.read(3), byteorder='big', signed=False) * 4096,
                int.from_bytes(region.read(1), byteorder='big', signed=False) * 4096
            ] for i in range(1024)]

            timestamps = region.read(4096)

            loc = locations[((chunk_pos[0] % Sizes.REGION_WIDTH) + (chunk_pos[1] % Sizes.REGION_WIDTH) * Sizes.REGION_WIDTH)]
            if self.debug:
                print('Loading', chunk_pos, 'from', region.name)
            chunk = self._load_binary_chunk_at(region, loc[0], loc[1])
            self.chunks[chunk_pos] = chunk

    def _load_binary_chunk_at(self, region_file, offset, max_size):
        region_file.seek(offset)
        datalen = int.from_bytes(region_file.read(4), byteorder='big', signed=False)
        compr = region_file.read(1)
        # print(region_file.tell()-5, datalen)
        decompressed = zlib.decompress(region_file.read(datalen-1))
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

    def _get_region_file(self, chunk_pos):
        return 'r.' + '.'.join([str(x) for x in self._get_region(chunk_pos)]) + '.mca'

    def _get_chunk(self, block_pos):
        return (math.floor(block_pos[0] / Sizes.CHUNK_WIDTH), math.floor(block_pos[2] / Sizes.CHUNK_WIDTH))

    def _get_region(self, chunk_pos):
        return (math.floor(chunk_pos[0] / Sizes.REGION_WIDTH), math.floor(chunk_pos[1] / Sizes.REGION_WIDTH))
