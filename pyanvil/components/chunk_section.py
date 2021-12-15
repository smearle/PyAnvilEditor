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

    def serialize(self):
        serial_section = self.raw_section
        dirty = any([b._dirty for b in self.blocks])
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
