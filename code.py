
import os

# ------------------------------------------------------------------
# User Settings
# ------------------------------------------------------------------

wait_timeout = 30
reading_interval = 1             # seconds
write_interval = 30 * 60         # minutes * seconds
           
# ThingSpeak Broker
# Store secrets in a `settings.toml` file.
THINGSPEAK_SERVER = os.getenv("THINGSPEAK_SERVER")
THINGSPEAK_CLIENT_ID = os.getenv("THINGSPEAK_CLIENT_ID")
THINGSPEAK_USER_NAME = THINGSPEAK_CLIENT_ID
THINGSPEAK_PASSWORD = os.getenv("THINGSPEAK_PASSWORD")
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
THINGSPEAK_WRITE_API_KEY = os.getenv("THINGSPEAK_WRITE_API_KEY")


# ------------------------------------------------------------------
# Import Libraries
# ------------------------------------------------------------------

# General Modules
import time as time
import board
import busio
import gc
import json

# Hardware Modules
from digitalio import DigitalInOut, Direction, Pull
from adafruit_bme280 import basic as adafruit_bme280
import adafruit_sgp40

# Display Modules
# Works with inexpensive SSD1306 I2C oleds available on AliExpress and Amazon
import terminalio
import displayio
from adafruit_display_text import bitmap_label as label
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.rect import Rect
import adafruit_displayio_ssd1306

# Network Modules
import socketpool
import wifi
import rtc
import adafruit_ntp
import adafruit_minimqtt.adafruit_minimqtt as MQTT


# ------------------------------------------------------------------
# Device Setup
# ------------------------------------------------------------------

displayio.release_displays()
pool = socketpool.SocketPool(wifi.radio)

# i2c = board.STEMMA_I2C()
i2c = busio.I2C(board.GP5, board.GP4, frequency=100000)
sgp = adafruit_sgp40.SGP40(i2c)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, 0x76)
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C) #, reset=oled_reset)


# SSD1306 OLED
preload_glyphs = (True)

WIDTH  = 128
HEIGHT = 64
BORDER = 3
ROTATION = 0

display = adafruit_displayio_ssd1306.SSD1306(
    display_bus, 
    width=WIDTH, 
    height=HEIGHT, 
    rotation=ROTATION
)
display.show(None)

print(f'Screen loaded.\n\n{dir(board)}\n')  # Print out board pins for reference.


# NTP Time
ntp = adafruit_ntp.NTP(pool, server = '0.pool.ntp.org', tz_offset = -7)
r = rtc.RTC()

days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

print(f'rtc loaded\n{time.time()}\n')  # Prints time stored in the RTC.

def set_clock_now():
  print('Getting time from NTP.\n')
  r.datetime = ntp.datetime

  time.sleep(2)
    
  print('New time set!')

  # print(f' NTP: {ntp.datetime}')
  # print(f' RTC: {r.datetime}')
  # print(f'Time: {time.localtime()}')
  print()


# MQTT Setup
the_broker = "ThingSpeak"

# Initialize a new MQTT Client object
io = MQTT.MQTT(
    broker = THINGSPEAK_SERVER,
    port = 1883,
    username = THINGSPEAK_USER_NAME,
    password = THINGSPEAK_PASSWORD,
    client_id = THINGSPEAK_CLIENT_ID,
    socket_pool = pool,
    # ssl_context = ssl.create_default_context(),
)

def new_message(client, topic, message):
    # Method called whenever user/feeds/led has a new value
    print(f'New message on {topic}: {message}')


io.on_message = new_message


# -------------------------------------------------------
# Main Program
# -------------------------------------------------------

set_clock_now()
print_stats = True

t = time.localtime()
# tm_wday = 0-6, 0 is Monday
# tm_mon = 1-12, 1 is January
print(f'It is: {days[t.tm_wday + 0]}, {months[t.tm_mon - 1]} {t.tm_mday} at {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}\n')

# To prevent the OLED from burning out text is only displayed for the
# difference between limit_max and limit_low.
# (ie limit_max - limit_low = time stats are displayed so, 6 - 4 = 2 sec display time.)
limit_max = 6  # Number of times times to loop through data collection.
limit_low = 2  # Below this number will not print.
limit = limit_max

# Set the time when data will be pushed to MQTT next.
next_interval = time.monotonic() + write_interval  # Time to wait for tramsmitting data.

# Main Loop
while True:
    # Collect Data
    ip_address = wifi.radio.ipv4_address
    temperature = bme280.temperature
    humidity = bme280.relative_humidity
    t = time.localtime()
    mono_time = time.monotonic()
    
    compensated_raw_gas = sgp.measure_raw(temperature=temperature, relative_humidity=humidity)
    voc_index = sgp.measure_index(temperature=temperature, relative_humidity=humidity)
    
    # Prepare text blocks
    date_block = f'{days[t.tm_wday]}, {months[t.tm_mon-1]} {t.tm_mday}'
    time_block = f'{t.tm_hour:02}:{t.tm_min:02}'  # :{t.tm_sec:02}'
    clock_block = f'{date_block:>9} at {time_block:<5} PST' # ({limit:02d})'
    data_block = f'R: {compensated_raw_gas} | I: {voc_index}'


    # Display text routine 
    if limit < limit_low:
        print_stats = False
    if print_stats:
        print(f'\n{voc_index:^20}\n')
        # print(f'{clock_block:^20} {data_block:^21}    {str(ip_address)} {limit:02d}')
    if not print_stats:
        print('\n')  #{limit:02d}')
    if limit <= 0:
        limit = limit_max + 1
        print_stats = True


    # MQTT Activity
    '''When next_interval is reached, publish to MQTT '''
    if mono_time < next_interval:
        pass

    if mono_time >= next_interval:
        print(f"\nConnecting to {the_broker}...")
        io.connect(clean_session=True)
        
        # Subscribe to topics (TODO needs to be setup for ThingSpeak)
        # print(f'\nSubscribing: {mqtt_topic}')
        # io.subscribe(mqtt_topic)

        # Poll for incoming messages
        # io.loop()
        
        # Data to publish (TODO: needs cleaning)
        utc_time = time.time()+28800
        ip_address = f'{ip_address}'

        temperature_f = (temperature*1.8)+32
        humidity = humidity
        compensated_raw_gas = compensated_raw_gas
        voc_index = voc_index

        thinkspeak_topic = "channels/" + THINGSPEAK_CHANNEL_ID + "/publish"
        thingspeak_payload = f'field1={temperature_f}&field2={humidity}&field3={compensated_raw_gas}&field4={voc_index}&status={clock_block}'

        print(f'\n{thinkspeak_topic}\n{thingspeak_payload}\n')
        io.publish(thinkspeak_topic, thingspeak_payload, False)
        
        # Cleanup and Reset next_interval
        gc.collect()
        print('Garbage Collected')
        next_interval = time.monotonic() + write_interval
    
    limit += -1
    time.sleep(1)

