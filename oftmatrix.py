from flask import render_template, redirect, request, abort
app = Flask(__name__)

from bulbtricks.matrix import Matrix
from bulbtricks.effects.waveeffect import WaveEffect
from bulbtricks.drivers.console import ConsoleDriver
from bulbtricks.effects.highlighteffect import HighlightEffect
from bulbtricks.bulbs.rampupbulb import RampUpBulb

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--minbrightness", default=5, type=int)
parser.add_argument("--maxbrightness", default=50,  type=int)
parser.add_argument('--delay', default=4, type=int)
args = parser.parse_args()

oftmatrix = Matrix(10,5)
try:
    from bulbtricks.drivers.olawebdriver import OLAWebDriver
    wd = OLAWebDriver(oftmatrix)
    wd.channel_map[35] = 10
except:
    print('failed to load OLAWebDriver')
d = ConsoleDriver(oftmatrix)
d.frequency = 30


def waveeffect(delay, minbrightness, maxbrightness):
    effect = WaveEffect(delay = delay, minbrightness = (minbrightness + 0.0)/100, maxbrightness = (maxbrightness+0.0)/100)
    oftmatrix.remove_all_effects()
    oftmatrix.add_effect(effect)


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

oftmatrix.run()
wd.run()
waveeffect(4, 5, 100)
app.run(debug=True, port=9143)
