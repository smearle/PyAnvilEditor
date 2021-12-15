class BlockState:
    def __init__(self, name: str = 'minecraft:air', props: dict = {}):
        self.name = name
        self.props = props
        self.id: int = None

    def __str__(self):
        return f'BlockState({self.name}, {str(self.props)})'

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name and self.props == other.props

    def clone(self):
        return BlockState(self.name, self.props.copy())
