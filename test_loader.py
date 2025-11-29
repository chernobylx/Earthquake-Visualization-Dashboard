from DataLoader import RequestParams as RP
from DataLoader import InvalidParamError, DT_FORMAT, DataLoader
from datetime import datetime, timedelta
from pytest import raises


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
        


class TestDataLoader:

    #test DataLoader.count 
    def test_count(self):
        #set start and endtimes
        starttime = datetime(year=2025,month=11,day=20)
        endtime = datetime(year=2025,month=11,day=21)
        #convert them to strings
        start = datetime.strftime(starttime, DT_FORMAT)
        end = datetime.strftime(endtime, DT_FORMAT)
        #construct params
        params = RP(starttime=start, endtime=end, minmagnitude=5)
        #validate params
        assert params.validate()
        dl = DataLoader(params) 
        assert dl.count() == 6