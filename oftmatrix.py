from flask import Flask, render_template, redirect, request, abort, jsonify
app = Flask(__name__)
import threading
import time

from bulbtricks.matrix import Matrix
from bulbtricks.effects.waveeffect import WaveEffect
from bulbtricks.effects import EffectCycler
from bulbtricks.effects.blinkeffect import BlinkColumnEffect
from bulbtricks.effects.pulseeffect import PulseEffect
from bulbtricks.drivers.console import ConsoleDriver
from bulbtricks.effects.highlighteffect import HighlightEffect
from bulbtricks.bulbs.rampupbulb import RampUpBulb
import logging

oftmatrix = Matrix(10,5)
try:
    from bulbtricks.drivers.olawebdriver import OLAWebDriver
    wd = OLAWebDriver(oftmatrix)
    wd.channel_map[35] = 10
except:
    print('failed to load OLAWebDriver')
d = ConsoleDriver(oftmatrix)
d.frequency = 15


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


def all_off():
    oftmatrix.remove_all_effects()
    for col in range(oftmatrix.columns):
        for row in range(oftmatrix.rows):
            cbulb = oftmatrix.at(col,row)
            rdbulb = RampUpBulb(delay=2, minbrightness=0, maxbrightness=cbulb.brightness)
            rdbulb.backward()
            rdbulb.brightness = cbulb.brightness
            oftmatrix.add(rdbulb, col, row)


def highlight():
    he = HighlightEffect(5, 3, minbrightnessmodifier = 0, delay = 10)
    oftmatrix.add_effect(he)

####web
@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/effect/wave', methods=['POST'])
def effect_wave():
    waveeffect(4, 5, 100)
    return jsonify({'status': 'ok'})
    
@app.route('/effect/party', methods=['POST'])
def effect_party():
    partyeffect()
    return jsonify({'status': 'ok'})
    
@app.route('/lights/all_off', methods=['POST'])
def lights_all_off():
    all_off()
    return jsonify({'status': 'ok'})
            
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
                flask.request.environ.get('werkzeug.server.shutdown')()
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
    oftmatrix.run()
    try:
        wd.run()
    except:
        pass
    waveeffect(4, 5, 100)
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
