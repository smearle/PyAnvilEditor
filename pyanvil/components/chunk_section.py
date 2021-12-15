import math
from . import Block, BlockState, Sizes
from . import ByteArrayTag, ByteTag, CompoundTag, StringTag, LongArrayTag, LongTag, ListTag


class ChunkSection:
    def __init__(self, blocks: dict[int, Block], raw_section, y_index):
        self.blocks: dict[int, Block] = blocks
        self.raw_section = raw_section
        self.y_index = y_index

    def get_block(self, block_pos):
        x = block_pos[0]
        y = block_pos[1]
        z = block_pos[2]

        return self.blocks[x + z * Sizes.SUBCHUNK_WIDTH + y * Sizes.SUBCHUNK_WIDTH ** 2]

    @staticmethod
    def from_nbt(section_nbt) -> 'ChunkSection':
        states = []  # Sections which contain only air have no states.
        if section_nbt.has('BlockStates'):
            flatstates = [c.get() for c in section_nbt.get('BlockStates').children]
            pack_size = (len(flatstates) * 64) // (Sizes.SUBCHUNK_WIDTH ** 3)
            states = [
                ChunkSection._read_width_from_loc(flatstates, pack_size, i) for i in range(Sizes.SUBCHUNK_WIDTH ** 3)
            ]
        palette: list[BlockState] = None
        if section_nbt.has('Palette'):
            palette = [
                BlockState(
                    state.get('Name').get(),
                    state.get('Properties').to_dict() if state.has('Properties') else {}
                ) for state in section_nbt.get('Palette').children
            ]
        block_lights = ChunkSection._divide_nibbles(section_nbt.get('BlockLight').get()) if section_nbt.has('BlockLight') else None
        sky_lights = ChunkSection._divide_nibbles(section_nbt.get('SkyLight').get()) if section_nbt.has('SkyLight') else None
        blocks = []
        for i, state in enumerate(states):
            state = palette[state]
            block_light = block_lights[i] if block_lights else 0
            sky_light = sky_lights[i] if sky_lights else 0
            blocks.append(Block(state=state, block_light=block_light, sky_light=sky_light))
        return ChunkSection(blocks, section_nbt, section_nbt.get('Y').get())

    def serialize(self):
        serial_section = self.raw_section
        dirty = any((b._dirty for b in self.blocks))
        if dirty:
            self.palette = list(set([b._state for b in self.blocks] + [BlockState('minecraft:air', {})]))
            self.palette.sort(key=lambda s: s.name)
            serial_section.add_child(ByteTag(tag_value=self.y_index, tag_name='Y'))
            mat_id_mapping = {self.palette[i]: i for i in range(len(self.palette))}
            new_palette = self._serialize_palette()
            serial_section.add_child(new_palette)
            serial_section.add_child(self._serialize_blockstates(mat_id_mapping))

        if not serial_section.has('SkyLight'):
            serial_section.add_child(ByteArrayTag(tag_name='SkyLight', children=[ByteTag(-1, tag_name='None') for i in range(2048)]))

        if not serial_section.has('BlockLight'):
            serial_section.add_child(ByteArrayTag(tag_name='BlockLight', children=[ByteTag(-1, tag_name='None') for i in range(2048)]))

        return serial_section

    def _serialize_palette(self):
        serial_palette = ListTag(CompoundTag.clazz_id, tag_name='Palette')
        for state in self.palette:
            palette_item = CompoundTag(tag_name='None', children=[
                StringTag(state.name, tag_name='Name')
            ])
            if len(state.props) != 0:
                serial_props = CompoundTag(tag_name='Properties')
                for name, val in state.props.items():
                    serial_props.add_child(StringTag(str(val), tag_name=name))
                palette_item.add_child(serial_props)
            serial_palette.add_child(palette_item)

        return serial_palette

    def _serialize_blockstates(self, state_mapping):
        serial_states = LongArrayTag(tag_name='BlockStates')
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
                block_index = long_index * states_per_long + (states_per_long - state - 1)

                if block_index < len(self.blocks):
                    block = self.blocks[block_index]
                    lng = (lng << width) + state_mapping[block._state]

            lng = int.from_bytes(lng.to_bytes(8, byteorder='big', signed=False), byteorder='big', signed=True)
            serial_states.add_child(LongTag(lng))
        return serial_states

    @staticmethod
    def _read_width_from_loc(long_list, width, position):
        # max amount of blockstates that fit in each long
        states_per_long = 64 // width

        # the long in which this blockstate is stored
        long_index = position // states_per_long

        # at which bit in the long this state is located
        position_in_long = (position % states_per_long) * width
        return ChunkSection._read_bits(long_list[long_index], width, position_in_long)

    @staticmethod
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

    @staticmethod
    def _divide_nibbles(arry):
        rtn = []
        f2_mask = (2 ** 4) - 1
        f1_mask = f2_mask << 4
        for s in arry:
            rtn.append(s & f1_mask)
            rtn.append(s & f2_mask)

        return rtn
