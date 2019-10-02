from flask import Flask, render_template, redirect, request, abort, jsonify
app = Flask(__name__)
import threading
import time

from bulbtricks.matrix import Matrix
from bulbtricks.effects.waveeffect import WaveEffect
from bulbtricks.effects.effect import EffectCycler
from bulbtricks.effects.blinkeffect import BlinkColumnEffect
from bulbtricks.effects.pulseeffect import PulseEffect
from bulbtricks.drivers.console import ConsoleDriver
from bulbtricks.effects.highlighteffect import HighlightEffect
from bulbtricks.bulbs.rampupbulb import RampUpBulb
from bulbtricks.bulbs.bulb import Bulb
import logging
import pickle
import os

class OFTMatrix(Matrix):
    def __init__(self, *args, **kwargs):
        Matrix.__init__(self, *args, **kwargs)
        self.brightness = 1.0
        
    def brightness_at(self, column, row):
        return Matrix.brightness_at(self, column, row) * self.brightness

oftmatrix = Matrix(10,5)
try:
    from bulbtricks.drivers.olawebdriver import OLAWebDriver
    wd = OLAWebDriver(oftmatrix)
    wd.channel_map[35] = 10
except:
    print('failed to load OLAWebDriver')
d = ConsoleDriver(oftmatrix)
d.frequency = 15

CONFIG = {}

def load_config():
    try:
        with open('oftmatrix.conf.pkl','rb') as f:
            return pickle.load(f)
    except:
        pass
    return {}
        
def save_config(config):
    try:
        with open('oftmatrix.conf.pkl','wb') as f:
            pickle.dump(config, f)
    except:
        pass
 
        
def set_current_effect(effect, parameters):
    CONFIG['current_effect'] = {'name': effect, 'params': parameters}
    save_config(CONFIG)
    
def set_status(status):
    CONFIG['status'] = status
    save_config(CONFIG)
    
def set_speed(speed):
    CONFIG['speed'] = speed
    oftmatrix._speed = speed
    save_config(CONFIG)
    
def set_brightness(brightness):
    CONFIG['brightness'] = brightness
    oftmatrix.brightness = brightness
    save_config(CONFIG)
    
def waveeffect(delay, minbrightness, maxbrightness):
    effect = WaveEffect(delay = delay, minbrightness = (minbrightness + 0.0)/100, maxbrightness = (maxbrightness+0.0)/100)
    oftmatrix.remove_all_effects()
    oftmatrix.add_effect(effect)
    
def partyeffect():
    cycler = EffectCycler()
    cycler.add_effect(BlinkColumnEffect(), 4)
    cycler.add_effect(BlinkColumnEffect(on_length=0.5, off_length=0.5), 2)
    cycler.add_effect(BlinkColumnEffect(), 2)
    cycler.add_effect(BlinkColumnEffect(), 4)
    cycler.add_effect(BlinkColumnEffect(on_length=0.5, off_length=0.5), 2)
    cycler.add_effect(BlinkColumnEffect(), 2)
    cycler.add_effect(PulseEffect(minbrightness = 1.0/255))
    cycler.add_effect(BlinkColumnEffect(on_length=0.5, off_length=0.5), 2)
    cycler.add_effect(PulseEffect(minbrightness = 1.0/255))
    cycler.add_effect(BlinkColumnEffect(on_length=0.5, off_length=0.5), 2)
    oftmatrix.remove_all_effects()
    oftmatrix.add_effect(cycler)
    
def noeffect(brightness=100):
    oftmatrix.remove_all_effects()
    for col in range(oftmatrix.columns):
        for row in range(oftmatrix.rows):
            rdbulb = Bulb()
            rdbulb.brightness = brightness/100.0
            oftmatrix.add(rdbulb, col, row)
    
       
EFFECTS = {
    "wave_effect": waveeffect,
    "party_mode": partyeffect,
    "none": noeffect
}

def activate_effect(effect, parameters={}):
    if effect in EFFECTS:
        EFFECTS[effect](**parameters)
        set_current_effect(effect, parameters)
        set_status(1)

def off():
    set_status(0)
    oftmatrix.remove_all_effects()
    for col in range(oftmatrix.columns):
        for row in range(oftmatrix.rows):
            cbulb = oftmatrix.at(col,row)
            rdbulb = RampUpBulb(delay=2, minbrightness=0, maxbrightness=cbulb.brightness)
            rdbulb.backward()
            rdbulb.brightness = cbulb.brightness
            oftmatrix.add(rdbulb, col, row)
            
def on():
    set_status(1)
    current_effect = CONFIG.get('current_effect')
    if not current_effect:
        current_effect = {
            'name': 'none',
            'params': {'brightness': 100}
        }
    activate_effect(current_effect.get('name'), current_effect.get('params',{}))

def highlight():
    he = HighlightEffect(5, 3, minbrightnessmodifier = 0, delay = 10)
    oftmatrix.add_effect(he)

####web
@app.route('/')
def index():
    return render_template('index.html', **{'matrix': oftmatrix})
    
@app.route('/control/state', methods = ['GET'])
def control_get_state():
    return 'ON' if CONFIG.get('status') else 'OFF'
    
@app.route('/control/state', methods = ['POST'])
def control_set_state():
    data = str(request.data or '','utf-8').lower().strip()
    if data == 'on':
        on()
    if data == 'off':
        off()
    return control_get_state()
    
@app.route('/control/brightness', methods = ['GET'])
def control_get_brightness():
    return int(oftmatrix.brightness * 255.0)
    
@app.route('/control/brightness', methods = ['POST'])
def control_set_brightness():
    brightness = -1
    try:
        brightness = max(0,min(255,int(str(request.data or '','utf-8'))))
    except:
        pass
    if brightness > -1:
        set_brightness(brightness / 255.0)
    return control_get_brightness()
    
@app.route('/effect/wave/<brightness>', methods=['POST'])
def effect_wave(brightness):
    try:
        brightness = int(brightness)
    except:
        brightness = 100
    activate_effect('wave_effect', {'delay': 4, 'minbrightness': 5, 'maxbrightness':brightness})
    return jsonify({'status': 'ok'})
    
@app.route('/effect/party', methods=['POST'])
def effect_party():
    activate_effect('party_mode')
    return jsonify({'status': 'ok'})
    
@app.route('/lights/all_off', methods=['POST'])
def lights_all_off():
    off()
    return jsonify({'status': 'ok'})
    
@app.route('/speed/<direction>', methods=['POST'])
def change_speed(direction):
    if direction in ('up','down'):
        dmod = 1
        if direction == 'down':
            dmod = -1
        set_speed(oftmatrix._speed + (0.1 * dmod))
        return jsonify({'status': 'ok', 'speed': str(int(oftmatrix._speed*100))})
    return jsonify({'status': 'fail'})
    
@app.route('/matrix', methods=['GET'])
def get_matrix():
    _matrix = [ [0 for x in range(0, oftmatrix.rows)] for y in range(0, oftmatrix.columns) ]
    for row in range(oftmatrix.rows):
        for col in range(oftmatrix.columns):
            try:
                _matrix[col][row] = int(oftmatrix.at(col,row).brightness * 100)
            except:
                pass
    return jsonify({'matrix': _matrix})
    
def initialize_matrix():
    set_speed(CONFIG.get('speed',1))
    if CONFIG.get('status'):
        on()
    oftmatrix.run()
            
class WebServerThread(threading.Thread):
    def __init__(self, app, port=9143):
        super(WebServerThread,self).__init__()
        self.port = int(port)
        self.app = app

    def run_server(self, **kwargs):
        logging.info('start server at: 127.0.0.1:%s' % self.port)
        @self.app.route('/stopwebserver') #todo this route should probably be randomized and only known to the server itself to prevent unauthorized shutdown
        def stop_server():
            self.app.logger.info('request received from {} to stop webserver thread'.format(request.remote_addr))
            if request.remote_addr == "127.0.0.1":
                request.environ.get('werkzeug.server.shutdown')()
            return abort(404)
        app.run(host='0.0.0.0', port = self.port)
    
    def stop_server(self, timeout=60):
        import requests
        try:
            requests.get('http://127.0.0.1:{}/stopwebserver'.format(self.port))
        except:
            pass

    def run(self):
        self.run_server()
        

def main():
    logging.getLogger().setLevel(logging.INFO)
    wsthread = WebServerThread(app)
    wsthread.start()
    global CONFIG
    CONFIG = load_config()
    logging.info('config loaded {}'.format(CONFIG))
    oftmatrix.run()
    try:
        wd.run()
    except:
        pass
    initialize_matrix()
    try:
        while 1:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("shutdown has been initiated from the console...")
        oftmatrix.stop()
        try:
            wd.stop()
        except:
            pass
        wsthread.stop_server()
    
if __name__ == '__main__':
    main()
