import glob
import os
import requests
import sqlite3
import time

from configparser import SafeConfigParser
from pyHS100 import Discover

database_file = 'data.db'
config_file = 'config.ini'

def read_temp_raw(device_file):
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    try:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

        base_dir = '/sys/bus/w1/devices/'
        device_folder = glob.glob(base_dir + '28*')[0]
        device_file = device_folder + '/w1_slave'

        lines = read_temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_f
    except:
        return 0;

def maybe_create_table():
    db = sqlite3.connect(database_file)
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Temps(id INTEGER PRIMARY KEY, ftemp_in REAL, ftemp_out REAL, timestamp INTEGER)
    ''')
    db.commit()

def print_db():
    db = sqlite3.connect(database_file)
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Temps")
    print(cursor.fetchall())
    db.commit()

def update_fan_state():
    maybe_create_table();
    ftemp_in = read_temp()
    print('ftemp_in', ftemp_in)

    config = SafeConfigParser()
    config.read('config.ini')

    PARAMS = {
        'lat': config.get('MAIN', 'LAT'),
        'lon': config.get('MAIN', 'LON'),
        'units': 'imperial',
        'APPID': config.get('MAIN', 'API_KEY')
    }

    r = requests.get(url = 'http://api.openweathermap.org/data/2.5/weather', params = PARAMS)
    ftemp_out = r.json()['main']['temp']
    print('ftemp_out', ftemp_out)

    db = sqlite3.connect(database_file)
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO Temps(ftemp_in, ftemp_out, timestamp) VALUES(?,?,?)
    ''', (ftemp_in, ftemp_out, int(time.time())))
    db.commit()

    threshold_temp_min = float(config.get('MAIN', 'THRESHOLD_TEMP_MIN'))
    threshold_temp_max = float(config.get('MAIN', 'THRESHOLD_TEMP_MAX'))
    for plug in Discover.discover().values():
        if (plug.state is not "ON" and ftemp_in > threshold_temp_max and ftemp_out < ftemp_in):
            print('Turning the fan on')
            plug.turn_on()
        elif (plug.state is not "OFF" and ftemp_in < threshold_temp_min):
            print('Turning the fan off')
            plug.turn_off()

update_fan_state();