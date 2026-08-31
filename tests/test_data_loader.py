from datetime import datetime

import pytest
import requests
from pytest import raises

from earthquake_dashboard.data_loader import (
    COL_TYPES,
    DT_FORMAT,
    DataLoader,
    InvalidParamError,
)
from earthquake_dashboard.data_loader import RequestParams as RP


def usgs_reachable() -> bool:
    try:
        requests.head(DataLoader.url, timeout=10)
        return True
    except requests.exceptions.RequestException:
        return False


# The DataLoader tests query the live USGS API; skip them when it is unreachable.
needs_usgs = pytest.mark.skipif(not usgs_reachable(), reason="USGS API unreachable")

starttime = datetime(year=2025,month=11,day=20)
endtime = datetime(year=2025,month=11,day=21)
#convert them to strings
start = datetime.strftime(starttime, DT_FORMAT)
end = datetime.strftime(endtime, DT_FORMAT)
#construct params
TEST_PARAMS = RP(starttime=start, endtime=end, minmagnitude=5)



class TestRequestParams:
    invalid_format_params: RP = RP(format='goojson')
    invalid_date_params: RP = RP(starttime=datetime.strftime(datetime(year=2025,month=1,day=1), DT_FORMAT), 
                                 endtime=datetime.strftime(datetime(year=2024,month=1,day=1), DT_FORMAT))
    
    def test_validate_format(self):
        with raises(InvalidParamError, match='format must be "geojson" not "goojson"'):
            self.invalid_format_params.validate()

    def test_validate_times(self):
        with raises(InvalidParamError, match="starttime must be before endtime"):
            self.invalid_date_params.validate()
        


@needs_usgs
class TestDataLoader:
    #test DataLoader.count
    #The USGS catalog is revised over time, so assert a floor rather than an exact
    #count: this window held 6 M5+ events when the test was written.
    def test_count(self):
        dl = DataLoader(TEST_PARAMS)
        assert dl.count() >= 6

    #test DataLoader.query -- the query must return exactly what count promised
    def test_query(self):
        dl = DataLoader(TEST_PARAMS)
        assert len(dl.query()) == dl.count()
    
    def test_preprocess(self):
        #test that the dataframe has the correct columns and datatypes required by the visualizer
        dl = DataLoader(TEST_PARAMS)
        dl.query()
        df = dl.preprocess()
        
        assert not df.empty, "Input DataFrame must not be empty"
        for col in COL_TYPES.keys():
            assert col in df.columns, f"DataFrame must contain '{col}' column"
        
        
        for col, expected_type in COL_TYPES.items():
            assert df[col].dtype == expected_type, f"Column '{col}' must be of type {expected_type}"


class TestCountDoesNotSendLimit:
    #The USGS count endpoint honours 'limit', so sending it makes the count
    #saturate at the cap: any larger window reports exactly 20,000 and the
    #query() guard can never fire. Offline test -- it inspects the outgoing
    #request rather than the live catalogue.
    def test_count_omits_limit(self, monkeypatch):
        sent = {}

        class FakeResponse:
            status_code = 200
            text = '{"count": 21753}'

        def fake_get(url, params=None, **kwargs):
            sent['url'] = url
            sent['params'] = params
            return FakeResponse()

        monkeypatch.setattr(requests, 'get', fake_get)

        assert DataLoader(TEST_PARAMS).count() == 21753
        assert 'limit' not in sent['params'], \
            "count() must not send 'limit': the endpoint honours it and the count saturates"
        #every other query parameter still has to reach the API
        assert sent['params']['minmagnitude'] == TEST_PARAMS.minmagnitude
        assert sent['params']['format'] == 'geojson'
