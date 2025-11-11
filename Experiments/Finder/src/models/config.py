import os
_MODEL_DIR_PATH = 'modeldirs/'
_DATA_DIR_PATH = 'datasets/'

# same params for all sizes
_DEFAULT_PARAMS = {
    'max_new_tokens': 1024,
    'temperature': 0.0,
    'top_p': 1.0
}


config = dict()
config['MODEL_DIR_PATH']=_MODEL_DIR_PATH

config['DATA_DIR_PATH']=_DATA_DIR_PATH
config['DEFAULT_PARAMS']=_DEFAULT_PARAMS




