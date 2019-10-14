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
from configreader import ConfigReader
import logging
import logging.handlers
import pickle
import os

def installThreadExcepthook():
    """
    Workaround for sys.excepthook thread bug
    From
    http://spyced.blogspot.com/2007/06/workaround-for-sysexcepthook-bug.html
       
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psyco.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    init_old = threading.Thread.__init__
    def init(self, *args, **kwargs):
        init_old(self, *args, **kwargs)
        run_old = self.run
        def run_with_except_hook(*args, **kw):
            try:
                run_old(*args, **kw)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                sys.excepthook(*sys.exc_info())
        self.run = run_with_except_hook
    threading.Thread.__init__ = init

class OFTMatrix(Matrix):
    def __init__(self, *args, **kwargs):
        Matrix.__init__(self, *args, **kwargs)
        self.brightness = 1.0
        
    def brightness_at(self, column, row):
        return Matrix.brightness_at(self, column, row) * self.brightness

oftmatrix = OFTMatrix(10,5)
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
    
def waveeffect(delay = 5, minbrightness= 5, maxbrightness=100):
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
    return str(int(oftmatrix.brightness * 255.0))
    
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
    
@app.route('/control/effect', methods = ['GET'])
def control_get_effect():
    return CONFIG.get('current_effect',{}).get('name','none')
    
@app.route('/control/effect', methods = ['POST'])
def control_set_effect():
    effect = str(request.data or '','utf-8')
    if effect in EFFECTS:
        activate_effect(effect)
    return control_get_effect()
    
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
                _matrix[col][row] = int(oftmatrix.brightness_at(col,row) * 100)
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
        try:
            self.run_server()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.excepthook(*sys.exc_info())
        
mainLogFormatter = logging.Formatter("%(asctime)s [%(levelname)s]: (%(name)s) %(message)s")
mainConsoleHandler = logging.StreamHandler()
mainConsoleHandler.setFormatter(mainLogFormatter)
logdir = "./logs/"

class BufferingSMTPHandler(logging.handlers.BufferingHandler):
    def __init__(self, smtpconfig, fromaddr, toaddrs, subject, capacity):
        logging.handlers.BufferingHandler.__init__(self, capacity)
        self.smtpconfig = smtpconfig
        self.fromaddr = fromaddr
        self.toaddrs = toaddrs
        self.subject = subject
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(message)s"))

    def flush(self):
        if len(self.buffer) > 0:
            try:
                import smtplib
                port = self.mailport
                if not port:
                    port = smtplib.SMTP_PORT
                smtp = smtplib.SMTP(self.smtpconfig.get('host'), self.smtpconfig.get('port'))
                if self.smtpconfig.get('username'):
                    smtp.login(self.smtpconfig.get('username'), self.smtpconfig.get('password'))
                msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n" % (self.fromaddr, string.join(self.toaddrs, ","), self.subject)
                for record in self.buffer:
                    s = self.format(record)
                    msg = msg + s + "\r\n"
                smtp.sendmail(self.fromaddr, self.toaddrs, msg)
                smtp.quit()
            except:
                self.handleError(None)  # no particular record
            self.buffer = []

def configure_log(logdir=logdir,level=logging.WARNING,name=None):
    logger = logging.getLogger(name)
    for hdlr in logger.handlers[:]:
        logger.removeHandler(hdlr)
    logger.setLevel(level)
    logger.propagate = False
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    filename = "oftmatrix.log"
    if name is not None:
        filename = "oftmatrix.{}.log".format(name)  
    fileHandler = logging.FileHandler(filename=os.path.join(logdir, filename))
    fileHandler.setFormatter(mainLogFormatter)
    logger.addHandler(fileHandler)
    logger.addHandler(mainConsoleHandler)
    config = ConfigReader()
    alertemails = config.get('logging','error_alertemails')
    if len(alertemails) > 0:
        smtpHandler = BufferingSMTPHandler(
            toaddrs=alertemails,
            fromaddr=config.get('logging','error_fromaddr'),
            smtpconfig=config.get('logging','smtpconfig'),
            subject="Error in OFTMatrix",
            capacity=10)
        smtpHandler.setFormatter(mainLogFormatter)
        smtpHandler.setLevel(logging.ERROR)
        logger.addHandler(smtpHandler)

def main():
    config = ConfigReader()
    loglevel = logging.INFO
    if config.get("logging","loglevel"):
        numeric_level = getattr(logging, config.get("logging","loglevel").upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        loglevel = numeric_level
    configure_log(level=loglevel)
    
    installThreadExcepthook()
    
    def uncaught_exception_handler(exc_type, exc_value, exc_traceback):
        logging.info('haha wtf {}'.format(exc_traceback))
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = uncaught_exception_handler
    
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
