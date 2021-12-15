from ..utility.nbt import NBT

ByteTag = NBT.create_simple_nbt_class(1, 'Byte', 1, '>b')
ShortTag = NBT.create_simple_nbt_class(2, 'Short', 2, '>h')
IntTag = NBT.create_simple_nbt_class(3, 'Int', 4, '>i')
LongTag = NBT.create_simple_nbt_class(4, 'Long', 8, '>q')
FloatTag = NBT.create_simple_nbt_class(5, 'Float', 4, '>f')
DoubleTag = NBT.create_simple_nbt_class(6, 'Double', 8, '>d')

ByteArrayTag = NBT.create_array_nbt_class(7, 'ByteArray', ByteTag)

StringTag = NBT.create_string_nbt_class(8)
ListTag = NBT.create_list_nbt_class(9)
CompoundTag = NBT.create_compund_nbt_class(10)

IntArrayTag = NBT.create_array_nbt_class(11, 'IntArray', IntTag)
LongArrayTag = NBT.create_array_nbt_class(12, 'LongArray', LongTag)
