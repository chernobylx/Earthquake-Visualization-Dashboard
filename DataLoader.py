import requests
from datetime import datetime, timedelta
import geopandas as gpd

#A Class for loading earthquake data from USGS API
class DataLoader:
    def __init__(self, params: dict):
        self.params = params
        self.url = "https://earthquake.usgs.gov/fdsnws/event/1/"
