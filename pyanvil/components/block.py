from . import BlockState
from .component_base import ComponentBase


class Block(ComponentBase):
    def __init__(self, state=BlockState(), block_light: int = 0, sky_light: int = 0, dirty: bool = False, parent_chunk_section: 'ChunkSection' = None):
        super().__init__(parent=parent_chunk_section, dirty=dirty)
        self._state: BlockState = state
        self.block_light: int = block_light
        self.sky_light: int = sky_light

    def __str__(self):
        return f'Block({str(self._state)}, {self.block_light}, {self.sky_light})'

    def set_state(self, state):
        self._dirty = True
        if type(state) is BlockState:
            self._state = state
        else:
            self._state = BlockState(state, {})
        self.mark_as_dirty()

    def get_state(self):
        return self._state.clone()
