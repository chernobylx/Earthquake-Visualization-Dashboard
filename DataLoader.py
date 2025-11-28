import requests
from datetime import datetime, timedelta
import geopandas as gpd

#A Class for loading earthquake data from USGS API
class DataLoader:
    def __init__(self, params: dict):
        for key in params.keys():
            assert key in ['starttime', 'endtime', 
                           'minlatitude', 'maxlatitude',
                           'minlongitude', 'maxlongitude',
                           'mindepth', 'maxdepth',
                           'minmagnitude', 'maxmagnitude',
                           'minsig', 'maxsig'], "Invalid parameter"
        
        self.params = params
        self.url = "https://earthquake.usgs.gov/fdsnws/event/1/"
