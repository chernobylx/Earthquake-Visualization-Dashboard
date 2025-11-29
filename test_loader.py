from DataLoader import RequestParams as RP
from DataLoader import InvalidParamError, DT_FORMAT, DataLoader, COL_TYPES
from datetime import datetime, timedelta
from pytest import raises

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
        


class TestDataLoader:
    def __init__(self):
        #set start and endtimes
        self.starttime = datetime(year=2025,month=11,day=20)
        self.endtime = datetime(year=2025,month=11,day=21)
        #convert them to strings
        self.start = datetime.strftime(starttime, DT_FORMAT)
        self.end = datetime.strftime(endtime, DT_FORMAT)
        #construct params
        self.params = RP(starttime=start, endtime=end, minmagnitude=5)
        self.params.validate()
    
    #test DataLoader.count 
    def test_count(self): 
        dl = DataLoader(TEST_PARAMS) 
        assert dl.count() == 6

    #test DataLoader.query
    def test_query(self):
        dl = DataLoader(TEST_PARAMS) 
        assert len(dl.query()) == 6
    
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
