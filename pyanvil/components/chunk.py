from . import ChunkSection, Sizes, Block, BlockState, Biome
from . import CompoundTag, ListTag


class Chunk:
    def __init__(self, xpos, zpos, sections: dict[int, ChunkSection], raw_nbt, orig_size):
        self.xpos = xpos
        self.zpos = zpos
        self.sections: dict[int, ChunkSection] = sections
        self.raw_nbt = raw_nbt
        self.biomes = [Biome.from_index(i) for i in self.raw_nbt.get('Level').get('Biomes').get()]
        self.orig_size = orig_size

    def get_block(self, block_pos):
        return self.get_section(block_pos[1]).get_block([n % Sizes.SUBCHUNK_WIDTH for n in block_pos])

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
                            results.append((
                                (x1 + self.xpos * Sizes.SUBCHUNK_WIDTH, y1 + sec * Sizes.SUBCHUNK_WIDTH, z1 + self.zpos * Sizes.SUBCHUNK_WIDTH),
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
                pack_size = int((len(flatstates) * 64) / (Sizes.SUBCHUNK_WIDTH ** 3))
                states = [
                    Chunk._read_width_from_loc(flatstates, pack_size, i) for i in range(Sizes.SUBCHUNK_WIDTH ** 3)
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
        new_sections = ListTag(CompoundTag.clazz_id, tag_name='Sections', children=[
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
        position_in_long = (position % states_per_long) * width
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
