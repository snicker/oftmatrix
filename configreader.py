import simplejson as json
import os
import logging

class ConfigReader(object):
    def __init__(self, configfile = None, globalconfigfile = None):
        if globalconfigfile is not None:
            os.environ['GLOBALCONFIG'] = globalconfigfile
        if configfile is None:
            configfile = os.environ.get('GLOBALCONFIG','config.json')
        self.configfile = configfile
        self._config_mtime = 0
        self._config = None
        self.refresh()
        
    def refresh(self,force=False):
        mtime = os.path.getmtime(self.configfile)
        if force or mtime > self._config_mtime or self._config is None:
            logging.debug("Loading Config: {}".format(self.configfile))
            with open(self.configfile) as data_file:    
                self._config = json.load(data_file)
            self._config_mtime = mtime

    def get(self, *args):
        self.refresh()
        value = self._config
        i = 0
        while i < len(args):
            key = args[i]
            i = i + 1
            if key in value:
                value = value[key]
            else:
                return None
        return value