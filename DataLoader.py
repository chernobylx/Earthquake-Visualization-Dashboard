import requests
import geopandas as gpd
from typing import Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

#A custom error class for validating GeoJSONRequestParams
class InvalidParamError(Exception):
    def __init__(self, message: str):
        self.message: str
        self.message = message
        super().__init__(self.message)


@dataclass 
class RequestParams:
    #a dataclass for storing geojson api request params for the usgs api at https://earthquake.usgs.gov/fdsnws/event/1/
    format: str = 'geojson' #format must be geojson

    #starttime must be before endtime if both are specified
    starttime: Optional[datetime] = datetime(year=2025, month=11, day=20)
    endtime: Optional[datetime]= datetime(year=2025, month=11, day=27)

    #minmagnitude must be less than maxmagnitude if both are specified
    minmagnitude: Optional[float] = 6.0
    maxmagnitude: Optional[float] = None

    #define a rectangle of coordinates to filter earthquakes
    minlatitude: Optional[float] = -90.0
    maxlatitude: Optional[float] = 90.0
    minlongitude: Optional[float] = -180.0
    maxlongitude: Optional[float] = 180.0

    #define a circle centered at latitude and longitude with radius maxradius or maxradiuskm
    #if both rectangle and circle are used the intersection is returned which may be empty
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    #maxradius and maxradiuskm cannot be used together
    maxradiuskm: Optional[float] = None #radius in km, must be in [0, 200001.6]
    maxradius: Optional[float] = None #radius in degress, must be in [0, 180]

    #requests are limited to a max of 20000 records
    limit: int = 20000
    offset: int = 1
    orderby: str = 'time' #

    mindepth: float = -100
    maxdepth: float = 1000

    minsig: Optional[int] = None
    maxsig: Optional[int] = None

    def validate(self):
        try:
            assert self.format == 'geojson', f'format must be "geojson" not {self.format}'
            
            if (self.starttime != None) and (self.endtime != None):
                assert self.starttime < self.endtime, "starttime must be before endtime"


            #TODO: if min{param} and max{param} assert min{param} < max{param}
            for param in ['latitude', 'longitude', 'magnitude', 'sig', 'depth']:
                if (self.__getattribute__(f'min{param}') != None) and (self.__getattribute__(f'max{param}') != None):
                   assert self.__getattribute__(f'min{param}') < self.__getattribute__(f'max{param}'), f'min{param} must be less than max{param}'
                   
        except AssertionError as e:
            raise InvalidParamError(str(e))
        else:
            return True




