#import modules
import Adafruit_BMP.BMP085 as BMP
import RPi.GPIO as GPIO
import sqlite3, time, datetime, sys, math, re, signal

#import dependencies
sys.path.append('./dep')
sys.path.append('./dep/Adafruit_ADS1x15')
import dht11, SDL_DS3231
import SDL_Pi_Weather_80422 as SDL80422

#variables
pinAnem = 23
pinRain = 24
DHTpin = 14

#initialize the GPIO for the DHT11 & set modes for wind/rain sensors
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
windrain = SDL80422.SDL_Pi_Weather_80422(pinAnem, pinRain, 0, 0, 1)
windrain.setWindMode(0, 5.0)

#sqlite
conn = sqlite3.connect('wxdata.db')
c = conn.cursor()
c.executescript('''
CREATE TABLE IF NOT EXISTS data (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    datetime TEXT UNIQUE,
    temp TEXT, 
    pres TEXT,
    hum TEXT,
    dewpoint TEXT,
    windspeed TEXT,
    windgust TEXT,
    winddir TEXT,
    dailyRain TEXT,
    heatindex TEXT,
    windchill TEXT)''')

def handler(signal, frame): #this shuts down the program when Ctrl-C is pressed 
    c.close()
    CURSOR_UP = '\033[F'
    ERASE_LINE = '\033[K'
    print(CURSOR_UP + ERASE_LINE)
    print 'Game over man'
    sys.exit(0)
signal.signal(signal.SIGINT, handler)

def get_temps(): #this function gets temp values from the bmp
    bmp = BMP.BMP085()
    tempc = bmp.read_temperature()
    tempc = round(tempc, 1)
    tempf = round(tempc*9/5+32, 1)
    return tempc, tempf

def get_pressure(): #this function gets pressure
    bmp = BMP.BMP085()
    pres = bmp.read_pressure()
    presin = round(pres/3386.39, 2) #(inHg)
    return presin	

def get_humidity(): #this function gets humidity
   humidity = 0
   while humidity < 1:
    dht = dht11.DHT11(pin=DHTpin)
    humidity = dht.read()
    humidity = humidity.humidity
   return humidity

def get_windraindata(date_time, prev_time, dailyRain): #this function gets wind & rain data
    windspeed = round(windrain.current_wind_speed()/1.6, 1)
    windgust = round(windrain.get_wind_gust()/1.6, 1)
    winddir = windrain.current_wind_direction()
    if winddir == 0: winddir = "N"
    if winddir == 22.5: winddir = "NNE"
    if winddir == 45: winddir = "NE"
    if winddir == 67.5: winddir = "ENE"
    if winddir == 90: winddir = "E"
    if winddir == 112.5: winddir = "ESE"
    if winddir == 135: winddir= "SE"
    if winddir == 157.5: winddir = "SSE"
    if winddir == 180: winddir = "S"
    if winddir == 202.5: winddir = "SSW"
    if winddir == 225: winddir = "SW"
    if winddir == 247.5: winddir = "WSW"
    if winddir == 270: winddir = "W"
    if winddir == 292.5: winddir = "WNW"
    if winddir == 315: winddir = "NW"
    if winddir == 337.5: winddir = "NNW"
    totalRain = windrain.get_current_rain_total()/25.4
    if prev_time.day == date_time.day:
     dailyRain += totalRain
     dailyRain = round(dailyRain, 2)
    else:
     dailyRain = 0
     dailyRain += totalRain
     dailyRain = round(dailyRain, 2)
    return windspeed, windgust, winddir, dailyRain

def get_datetime(): #this function gets the realtime datetime
    rtc = SDL_DS3231.SDL_DS3231(1, 0x68)    
    date_time = rtc.read_datetime()
    return date_time

def calc_dewpoint(tempc, humidity): #this function calculates the dewpoint
    dewpoint = 243.04*(math.log(humidity/100.0)+((17.625*tempc)/(243.04+tempc)))/(17.625-(math.log(humidity/100.0))-((17.625*tempc)/(243.04+tempc)))
    dewpointf = round(dewpoint*9.0/5+32, 1) #(*F)
    return dewpointf

def calc_windchill(): #calculates windchill if windspeed >=3 & tempc <=10 
    if windspeed >= 3 and tempc <= 10:
     windchill = 35.74+0.6215*tempc-35.75*math.pow(windspeed, 0.16)+0.4275*tempc*math.pow(windspeed, 0.16)
     windchillf = windchill*9/5.0-32 #(*F)
     return round(windchillf, 1)
    else: return None

def calc_heatindex(): #This calculates the heat index if tempf >= 80*F & humidity > 40%
    if tempf >= 80 and humidity >=40:
     heatindex = -42.379+2.04901523*tempf+10.14333127*humidity-0.22475541*tempf*humidity-0.00683783*tempf*tempf-.05481717*humidity*humidity+.00122874*tempf*tempf*humidity+.00085282*tempf*humidity*humidity-.00000199*tempf*tempf*humidity*humidity
     return round(heatindex, 1)
    else: return None

#this checks the databases' last date to determine if daily rain totals needed
c.execute('SELECT datetime FROM data WHERE ID = (SELECT MAX(ID) FROM data)')
prevtime = c.fetchone()[0]
prevtime = prevtime.split( ) #this is necessary because we only want the date and not the time
prevtime = str(prevtime[0])
today = str(datetime.date.today())
if today == prevtime:
 c.execute('SELECT dailyRain FROM data WHERE ID = (SELECT MAX(ID) FROM data)')
 dailyRain = float(c.fetchone()[0])
else: dailyRain = 0.0

#opening banner - shitty but it'll do
date_time = get_datetime()
format = '%a %b %d %Y at %H:%M:%S' # for date & time formatting
fdatetime = date_time.strftime(format)
print "__________________________________________________________________"
print "-----------------------Mike's Weather Station!--------------------" 
print "------------------------------------------------------------------"
print "                Started %s" % fdatetime
print "__________________________________________________________________"

#main program
while True:
  #get & calculate all values
  prev_time = date_time
  date_time = get_datetime()
  tempc, tempf = get_temps()
  presin = get_pressure()
  humidity = get_humidity()
  windspeed, windgust, winddir, dailyRain = get_windraindata(prev_time, date_time, dailyRain)
  dewpointf = calc_dewpoint(tempc, humidity)
  windchillf = calc_windchill()
  heatindex = calc_heatindex()
  #Write data to sql
  c.execute('INSERT INTO data (datetime, temp, pres, hum, dewpoint, windspeed, windgust, winddir, heatindex, windchill, dailyRain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (date_time, tempf, presin, humidity, dewpointf, windspeed, windgust, winddir, heatindex, windchillf, dailyRain))
  conn.commit()
  #Print data
  print 'Date & Time:\t\t %s' % date_time 
  print 'Temperature =\t\t %.1f *F' % tempf #(*C->*F)
  print 'Pressure    =\t\t %.2f inHg' % presin #(Pa->inHg)
  print 'Humidity    =\t\t %.0f %%' % humidity #(%RH)
  print 'Wind Speed  =\t\t %.1f MPH' % windspeed #(MPH)
  print 'Wind Dir.   =\t\t %s' % winddir 
  print 'Daily Rain  =\t\t %.2f in' % dailyRain #(in)
  print 'Dew Point   =\t\t %.1f *F' % dewpointf #(*F)
  if windchillf is not None:
   print 'Wind Chill  =\t\t %.1f *F' % windchillf #(*F)
  if heatindex is not None:
   print 'Heat Index  =\t\t %.1f *F' % heatindex #(*F)
  print '------------------------------------------------------------------'
  time.sleep(60)

