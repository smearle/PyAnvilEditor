#!/bin/python3
from pyanvil import World, BlockState, Material

with World('A', save_location='/home/dallen/.minecraft/saves', debug=True) as wrld:
    myBlockPos = (15, 10, 25)
    myBlock = wrld.get_block(myBlockPos)
    myBlock.set_state(BlockState('minecraft:iron_block'))
print('Saved!')
