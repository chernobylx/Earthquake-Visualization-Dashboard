from DataLoader import RequestParams as RP
from DataLoader import InvalidParamError
from datetime import datetime, timedelta
from pytest import raises


class TestRequestParams:
    invalid_format_params: RP = RP(format='goojson')
    invalid_date_params: RP = RP(starttime=datetime(year=2025,month=1,day=1), 
                                 endtime=datetime(year=2024,month=1,day=1))
    
    def test_validate_format(self):
        with raises(InvalidParamError, match='format must be "geojson" not "goojson"'):
            self.invalid_format_params.validate()

    def test_validate_times(self):
        with raises(InvalidParamError, match="starttime must be before endtime"):
            self.invalid_date_params.validate()
        


