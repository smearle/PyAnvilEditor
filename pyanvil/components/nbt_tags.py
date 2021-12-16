from ..utility.nbt import NBT
from ..utility.nbt import TagType

ByteTag = NBT.create_simple_nbt_class(TagType.BYTE, 'Byte', 1, '>b')
ShortTag = NBT.create_simple_nbt_class(TagType.SHORT, 'Short', 2, '>h')
IntTag = NBT.create_simple_nbt_class(TagType.INT, 'Int', 4, '>i')
LongTag = NBT.create_simple_nbt_class(TagType.LONG, 'Long', 8, '>q')
FloatTag = NBT.create_simple_nbt_class(TagType.FLOAT, 'Float', 4, '>f')
DoubleTag = NBT.create_simple_nbt_class(TagType.DOUBLE, 'Double', 8, '>d')

ByteArrayTag = NBT.create_array_nbt_class(TagType.BYTE_ARRAY, 'ByteArray', ByteTag)

StringTag = NBT.create_string_nbt_class(TagType.STRING)
ListTag = NBT.create_list_nbt_class(TagType.LIST)
CompoundTag = NBT.create_compund_nbt_class(TagType.COMPOUND)

IntArrayTag = NBT.create_array_nbt_class(TagType.INT_ARRAY, 'IntArray', IntTag)
LongArrayTag = NBT.create_array_nbt_class(TagType.LONG_ARRAY, 'LongArray', LongTag)
