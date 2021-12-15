from . import BlockState


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
