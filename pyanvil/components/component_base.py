from abc import ABC


class ComponentBase(ABC):
    def __init__(self, parent=None, dirty=False):
        '''Handles "dirty" propagation up the component chain.'''
        self._parent: ComponentBase = parent
        self._is_dirty: bool = dirty
        self._dirty_children: set = set()

    @property
    def is_dirty(self):
        return self._is_dirty

    def mark_as_dirty(self):
        self._is_dirty = True
        if self._parent is not None:
            self._parent.mark_child_as_dirty(self)
            self._parent.mark_as_dirty()

    def mark_child_as_dirty(self, child):
        self._dirty_children.add(child)

    def set_parent(self, parent: 'ComponentBase'):
        self._parent = parent
