#!/bin/python3
from pyanvil import World, BlockState
from pyanvil.coordinate import AbsoluteCoordinate

with World('A', save_location='/home/dallen/.minecraft/saves', debug=True) as wrld:
    myBlock = wrld.get_block(AbsoluteCoordinate(15, 10, 25))
    myBlock.set_state(BlockState('minecraft:iron_block'))
print('Saved!')
