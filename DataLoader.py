import pandas as pd
from io import StringIO
import requests
import json
import geopandas as gpd
from typing import Union
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
#Datetime format for the project
DT_FORMAT = "%y-%m-%d %H:%M:%S"

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
    starttime: Optional[str] = datetime.strftime(datetime(year=2025, month=11, day=20), DT_FORMAT)
    endtime: Optional[str]= datetime.strftime(datetime(year=2025, month=11, day=27), DT_FORMAT)

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
            assert self.format == 'geojson', f'format must be "geojson" not "{self.format}"'
            
            if (self.starttime != None) and (self.endtime != None):
                start = datetime.strptime(self.starttime, DT_FORMAT)
                end = datetime.strptime(self.endtime, DT_FORMAT)
                assert start < end, "starttime must be before endtime"


            #TODO: if min{param} and max{param} assert min{param} < max{param}
            for param in ['latitude', 'longitude', 'magnitude', 'sig', 'depth']:
                if (self.__getattribute__(f'min{param}') != None) and (self.__getattribute__(f'max{param}') != None):
                   assert self.__getattribute__(f'min{param}') < self.__getattribute__(f'max{param}'), f'min{param} must be less than max{param}'
                   
        except AssertionError as e:
            raise InvalidParamError(str(e))
        else:
            return True




class DataLoader:
    url: str = 'https://earthquake.usgs.gov/fdsnws/event/1/'
    count_url: str = url + 'count'
    query_url: str = url + 'query'
    def __init__(self, params: RequestParams) -> None:
        assert params.validate()
        self.params = params

    def count(self)->int: 
        #performs a get request using count_url and params
        #returns the number of records that would be returned in a query
        try:
            self.response = requests.get(self.count_url, self.params.__dict__)
            if self.response.status_code != 200:
                raise Exception(f'HTTP Request Error: {self.response.status_code}')
        except Exception as e:
            raise Exception(str(e))
        else:
            self.body = json.loads(self.response.text)
            return self.body['count']
    
    def query(self)->gpd.GeoDataFrame:
        try: 
            COUNT = self.count()
            assert COUNT <= 20000, "Queries cannot exceed 20,000 records"
            self.response = requests.get(self.query_url, self.params.__dict__)
            if self.response.status_code != 200:
                raise Exception(f"HTTP Request Error: {self.response.status_code}")
        except Exception as e:
            raise Exception(str(e))
        else:
            self.gdf = gpd.read_file(StringIO(self.response.text))
            return self.gdf
    
    def preprocess(self):
        self.gdf['lon'] = self.gdf.geometry.x
        self.gdf['lat'] = self.gdf.geometry.y
        self.gdf['depth'] = self.gdf.geometry.z
        self.gdf.rename({'magnitude': 'mag', 'significance': 'sig'}, inplace=True)
        self.gdf['sig'] = self.gdf['sig'].astype(int)
        self.gdf['time'] = pd.to_datetime(self.gdf['time'])
        self.gdf['tsunami'] = self.gdf['tsunami'].astype(bool)
        return self.gdf

