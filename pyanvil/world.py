from typing import Union
from pathlib import Path

from .components.region import Region
from .coordinate import AbsoluteCoordinate, ChunkCoordinate, RegionCoordinate
from .canvas import Canvas
from .components import Chunk, Block


class World:
    def __init__(self, world_folder, save_location=None, debug=False, read=True, write=True):
        self.debug = debug
        self.world_folder = self.__resolve_world_folder(world_folder=world_folder, save_location=save_location)
        self.regions: dict[RegionCoordinate, Region] = dict()

    def __resolve_world_folder(self, world_folder: Union[str, Path], save_location: Union[str, Path]):
        folder = Path()
        if save_location is not None:
            folder = Path(save_location) / world_folder
        else:
            folder = Path(world_folder)
        if not folder.is_dir():
            raise FileNotFoundError(f'No such folder \"{folder}\"')
        return folder

    def __enter__(self) -> 'World':
        return self

    def __exit__(self, typ, val, trace):
        if typ is None:
            self.close()

    def flush(self):
        self.close()
        self.regions: dict[RegionCoordinate, Region] = dict()

    def close(self):
        for region in self.regions.values():
            if region.is_dirty:
                region.save()

    def get_block(self, coordinate: AbsoluteCoordinate) -> Block:
        self._get_region_file_name(coordinate.to_region_coordinate())
        chunk = self.get_chunk(coordinate.to_chunk_coordinate())
        return chunk.get_block(coordinate)

    def get_region(self, coord: RegionCoordinate):
        return self.regions.get(coord, self._load_region(coord))

    def get_chunk(self, coord: ChunkCoordinate) -> Chunk:
        region = self.get_region(coord.to_region_coordinate())
        return region.get_chunk(coord)

    def get_canvas(self):
        return Canvas(self)

    def _load_region(self, coord: RegionCoordinate):
        name = self._get_region_file_name(coord)
        region = Region(self.world_folder / 'region' / name)
        self.regions[coord] = region
        return region

    def _get_region_file_name(self, region: RegionCoordinate):
        return f'r.{region.x}.{region.z}.mca'
