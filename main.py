import sys, world

with world.World("New World", save_location="/home/dallen/snap/minecraft/common/.minecraft/saves") as world:
    # results = world.get_chunk((6, 6)).find_like("redstone_wall_torch")
    # for r in results:
    #     print(r[0], r[1])
    #     print((r[0][0] % 16) + (r[0][2] % 16) * 16 + (r[0][1] % 16) * 16 ** 2)
    b1 = world.get_block((100, 5, 100))
    b2 = world.get_block((100, 4, 99))
    b1.set_state(b2.get_state())
    print(b1, b2)