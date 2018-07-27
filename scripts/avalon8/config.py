
DEBUG = False

config = {
    'data_dir': './data',
    'time_delta': 10 if DEBUG else 60*2,
    'log_server': 'http://192.168.1.58:6000' if DEBUG else 'http://pd.canaan-creative.com',
}
