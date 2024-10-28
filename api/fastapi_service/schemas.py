from pydantic import BaseModel
from typing import Optional, List


class PointBase(BaseModel):
    longitude : float
    latitude : float

class PropertyBase(BaseModel):
    population : int
    population_density : Optional[float]
    c_longitude : float
    c_latitude : float
    time_zone : str
    time_created : str

class CityBase(BaseModel):
    id : int 
    city_name : str 
    property : Optional[PropertyBase] = None
    downloaded : Optional[bool] = False

class RegionBase(BaseModel):
    id : int
    admin_level : int
    name : str
    regions : List[List[List[float]]]

class GraphBase(BaseModel):
    edges_csv : str
    points_csv : str
    ways_properties_csv : str
    points_properties_csv : str
    reversed_edges_csv : str
    reversed_nodes_csv : str
    # reversed_matrix_csv : str



    

