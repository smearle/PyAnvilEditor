from pyanvil import BlockState, World
from pyanvil.coordinate import AbsoluteCoordinate


def test_block_place():
    # Load the world folder relative to the current working dir
    with World('world') as myWorld:
        # All locations are stored as tuples
        myBlockPos = AbsoluteCoordinate(15, 10, 25)
        # Get the block object at the given location
        myBlock = myWorld.get_block(myBlockPos)
        # Set the state of the block to an iron block
        myBlock.set_state(BlockState('minecraft:diamond_block', {}))
    # Once the with closes, the world is saved

    with World('world') as myWorld:
        # All locations are stored as tuples
        myBlockPos = AbsoluteCoordinate(15, 10, 25)
        # Get the block object at the given location
        myBlock = myWorld.get_block(myBlockPos)
        assert myBlock.get_state().name == 'minecraft:diamond_block'
