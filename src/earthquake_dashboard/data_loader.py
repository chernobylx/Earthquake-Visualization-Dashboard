import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Optional

import geopandas as gpd
import pandas as pd
import requests

#Datetime format for the project
DT_FORMAT = "%Y-%m-%d %H:%M:%S"

# How far back the default query window reaches, and the one place this package
# reads the current day.
#
# Both bounds used to be literals -- datetime(2025, 11, 20) and a week later --
# and a dataclass default is evaluated once, at class definition. So the window
# never moved: by the time anyone read it, it named a week already in the past.
# Both front-ends send dates of their own, so this only ever reached a library
# caller, and it reached them silently.
#
# The end bound is tomorrow rather than today because USGS reads a bare date as
# 00:00 UTC and therefore excludes the end date itself. A window ending today
# stops before today's events.
DEFAULT_WINDOW_DAYS = 30


def utc_today() -> date:
    """Today's date in UTC.

    Not ``date.today()``, which is the host's local day: on a host behind UTC
    the two disagree for part of every day, and every date this app shows or
    sends is UTC.
    """
    return datetime.now(timezone.utc).date()


def default_window() -> tuple[str, str]:
    """``(starttime, endtime)`` for the last month, ending tomorrow at 00:00 UTC."""
    today = utc_today()
    start = datetime.combine(today - timedelta(days=DEFAULT_WINDOW_DAYS), time.min)
    end = datetime.combine(today + timedelta(days=1), time.min)
    return start.strftime(DT_FORMAT), end.strftime(DT_FORMAT)


#columns and their types expected by the datavisuzlizer
COL_TYPES = {'place': 'object',
            'time': 'datetime64[ns, UTC]',
            'lat': 'float64',
            'lon': 'float64',
            'mag': 'float64',
            'sig': 'int64',
            'depth': 'float64',
            'tsunami': 'bool',
            'cdi': 'float64',
            'alert': 'object',
            # The event's page on earthquake.usgs.gov. USGS ships it with every
            # feature, so it costs nothing to carry, and it is what lets the map
            # link a point to its source record.
            'url': 'object',
}

# Vega applies no type inference to a CSV source, and Vega-Lite only fills in a
# parse for fields it encodes itself -- the heatmap converts time with its own
# toDate() calculate, so that stream got none and every column arrived as text.
# A brush then compared an ISO string against epoch milliseconds (NaN, so the
# heatmap emptied) and max(mag) was a lexicographic max. Front-ends that serve
# the frame by URL declare this alongside the data; inline JSON is already typed.
VEGA_PARSE_KINDS = {'datetime64[ns, UTC]': 'date',
                    'float64': 'number',
                    'int64': 'number',
                    'bool': 'boolean',
}


# Columns that ride along for a chart to use rather than for anyone to read. A
# full USGS event URL is around sixty characters and both front-ends' tables wrap
# their cells, so showing it makes every row several lines tall and squeezes the
# columns somebody is actually looking at. The map links each point instead.
HIDDEN_COLUMNS = ('url',)


def vega_parse() -> dict[str, str]:
    """The Vega ``format.parse`` map implied by COL_TYPES.

    Text columns are left out: Vega reads CSV fields as strings already.
    """
    return {col: VEGA_PARSE_KINDS[dtype]
            for col, dtype in COL_TYPES.items()
            if dtype in VEGA_PARSE_KINDS}
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

    #starttime must be before endtime if both are specified.
    #Read per instance through a factory, not written as a literal: a plain
    #dataclass default is computed once when this class is defined, which is how
    #the old hardcoded November 2025 window got stuck there. See default_window.
    starttime: Optional[str] = field(default_factory=lambda: default_window()[0])
    endtime: Optional[str] = field(default_factory=lambda: default_window()[1])

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
            
            if (self.starttime is not None) and (self.endtime is not None):
                start = datetime.strptime(self.starttime, DT_FORMAT)
                end = datetime.strptime(self.endtime, DT_FORMAT)
                assert start < end, "starttime must be before endtime"


            #TODO: if min{param} and max{param} assert min{param} < max{param}
            for param in ['latitude', 'longitude', 'magnitude', 'sig', 'depth']:
                if (self.__getattribute__(f'min{param}') is not None) and (self.__getattribute__(f'max{param}') is not None):
                   assert self.__getattribute__(f'min{param}') < self.__getattribute__(f'max{param}'), f'min{param} must be less than max{param}'
                   
        except AssertionError as e:
            raise InvalidParamError(str(e)) from e
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
            #the count endpoint honours 'limit', so sending it makes the count
            #saturate at the cap and report 20000 for any larger window. Drop it
            #here: without an honest count the query() guard below can never fire
            #and an oversized query is silently truncated instead of refused.
            count_params = {k: v for k, v in self.params.__dict__.items() if k != 'limit'}
            self.response = requests.get(self.count_url, count_params)
            if self.response.status_code != 200:
                raise Exception(f'HTTP Request Error: {self.response.status_code}')
        except Exception as e:
            raise Exception(str(e)) from e
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
            raise Exception(str(e)) from e
        else:
            self.gdf = gpd.read_file(StringIO(self.response.text))
            return self.gdf
    
    def preprocess(self):
        self.gdf['lon'] = self.gdf.geometry.x
        self.gdf['lat'] = self.gdf.geometry.y
        self.gdf['depth'] = self.gdf.geometry.z
        self.gdf.rename({'magnitude': 'mag', 'significance': 'sig'}, inplace=True)
        self.gdf['sig'] = self.gdf['sig'].astype(int)
        self.gdf['time'] = pd.to_datetime(self.gdf['time'], unit = 'ms', utc = True)
        self.gdf['tsunami'] = self.gdf['tsunami'].astype(bool)
        return self.gdf[COL_TYPES.keys()]

