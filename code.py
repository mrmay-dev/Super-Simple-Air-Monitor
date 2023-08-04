
import os

# ------------------------------------------------------------------
# User Settings
# ------------------------------------------------------------------

my_timezone = -7
reading_interval = 1             # seconds
write_interval = 30 * 60         # minutes * seconds
           
# ThingSpeak Broker
# Store secrets in a `settings.toml` file.
THINGSPEAK_SERVER = os.getenv("THINGSPEAK_SERVER")
THINGSPEAK_PORT = 1883
THINGSPEAK_CLIENT_ID = os.getenv("THINGSPEAK_CLIENT_ID")
THINGSPEAK_USER_NAME = THINGSPEAK_CLIENT_ID
THINGSPEAK_PASSWORD = os.getenv("THINGSPEAK_PASSWORD")
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
THINGSPEAK_WRITE_API_KEY = os.getenv("THINGSPEAK_WRITE_API_KEY")
THINGSPEAK_TOPIC = "channels/" + THINGSPEAK_CHANNEL_ID + "/publish"

# To prevent the OLED from burning out text is only displayed for the
# difference between limit_max and limit_low.
# (ie limit_max - limit_low = time stats are displayed so, 
# 3 - 1 = 2 sec display time.)
limit_visible = 3  # Number of visible iterations.
limit_low = 1  # Number of not visible iterations.

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
import rtc
from digitalio import DigitalInOut, Direction, Pull
from adafruit_bme280 import basic as adafruit_bme280
import adafruit_sgp40

# Display Modules
# Works with inexpensive SSD1306 I2C oleds available on AliExpress and Amazon
import terminalio
import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import bitmap_label as label
from adafruit_display_shapes.rect import Rect
import adafruit_displayio_ssd1306

# Network Modules
import wifi
import socketpool
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
WIDTH  = 128
HEIGHT = 64
BORDER = 0
ROTATION = 0

display = adafruit_displayio_ssd1306.SSD1306(
    display_bus, 
    width=WIDTH, 
    height=HEIGHT, 
    rotation=ROTATION
)

display.show(None)

JUNCTION_24 = bitmap_font.load_font("fonts/Junction-regular-24.bdf")
TERMINAL_FONT = terminalio.FONT

# display.rotation = ROTATION
main_group = displayio.Group()
display.show(main_group)

print(f'Screen loaded.\n\n{dir(board)}\n') 


# NTP Time
ntp = adafruit_ntp.NTP(pool, server = '0.pool.ntp.org', tz_offset = my_timezone)
r = rtc.RTC()

days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

print(f'rtc loaded\n{time.time()}\n')  # Prints time stored in the RTC.

def get_datetime():
    t = time.localtime()
    # tm_wday = 0-6, 0 is Monday
    # tm_mon = 1-12, 1 is January
    current_datetime = (f'It is: {days[t.tm_wday + 0]}, {months[t.tm_mon - 1]} {t.tm_mday} at {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}\n')
    return current_datetime
    

def set_clock_now():
  print('Getting time from NTP.\n')
  r.datetime = ntp.datetime
  time.sleep(1)
  print('New time set!')


# MQTT Setup
the_broker = "ThingSpeak"

# Initialize a new MQTT Client object
io = MQTT.MQTT(
    broker = THINGSPEAK_SERVER,
    port = THINGSPEAK_PORT,
    username = THINGSPEAK_USER_NAME,
    password = THINGSPEAK_PASSWORD,
    client_id = THINGSPEAK_CLIENT_ID,
    socket_pool = pool,
    # ssl_context = ssl.create_default_context(),
)
''' For future use
def new_message(client, topic, message):
    # Method called whenever user/feeds/led has a new value
    print(f'New message on {topic}: {message}')

io.on_message = new_message
'''

# -------------------------------------------------------
# Main Program
# -------------------------------------------------------
set_clock_now()
current_datetime = get_datetime()
print(current_datetime)

# Main Loop
# --------------------------

limit_max = limit_low + limit_visible
limit = limit_max
next_interval = time.monotonic() + write_interval  # Set the time when data will be pushed to MQTT next.
while True:
    # Collect Data
    ip_address = str(wifi.radio.ipv4_address)
    mono_time = time.monotonic()
    t = time.localtime()
    
    temperature = bme280.temperature  # Temperature in Celcious
    temperature_f = (temperature*1.8)+32  # Temperature in Fahrenheit
    humidity = bme280.relative_humidity
    
    compensated_raw_gas = sgp.measure_raw(temperature=temperature, relative_humidity=humidity)
    voc_index = sgp.measure_index(temperature=temperature, relative_humidity=humidity)

    
    # Prepare text blocks
    date_block = f'{days[t.tm_wday]}, {months[t.tm_mon-1]} {t.tm_mday}, {t.tm_year}'
    time_block = f'{t.tm_hour:02}:{t.tm_min:02}'  # :{t.tm_sec:02}'
    clock_block = f'{date_block:>9} at {time_block:<5} PST' 
    data_block = f'R: {compensated_raw_gas} | I: {voc_index}'

    # Print text routine 
    print_stats = True
    if limit <= limit_low:
        print_stats = False
    
    print_line = f'\n\n{clock_block:<20} [{data_block}]  {ip_address} \n({print_stats} {limit}/{limit_low}) \nNext Publish: {time.monotonic() - next_interval}'  # Print to REPL
    
    if print_stats:
        print(print_line)  # Print to REPL
        
        # Print to OLED display
        rect = Rect(0, 0, WIDTH, HEIGHT, fill=0x000000, outline=0x000000)
        main_group.append(rect)
        page_body = label.Label(
            JUNCTION_24,
            scale = 1,
            text = f'{voc_index}',
            anchor_point = (.5, .5),
            anchored_position = (WIDTH / 2 , (HEIGHT / 2)),
        )
        main_group.append(page_body)
        # show the group
        display.show(main_group)
    
    if not print_stats:
        print(print_line)  # Print to REPL
        
        # Print empty box to the OLED display
        rect = Rect(0, 0, WIDTH, HEIGHT, fill=0x000000, outline=0x000000)
        main_group.append(rect)
        page_body = label.Label(
            JUNCTION_24,
            scale = 1,
            text = f'',
            anchor_point = (.5, .5),
            anchored_position = (WIDTH / 2 , HEIGHT / 2),
        )
        main_group.append(page_body)
        # show the group
        display.show(main_group)
        

    # MQTT Activity
    '''When next_interval is reached, publish to MQTT '''
    if mono_time < next_interval:  # Not needed, but helps me to be explicit
        pass

    if mono_time >= next_interval:
        print(f"\nConnecting to {the_broker}...")

        # Prepare MQTT Payload:
        air_quality = ''
        if voc_index < 400:
            air_quality = 'Yuck! (250 - 400)'
        if voc_index < 250:
            air_quality = 'Meh. (150 - 249)'
        if voc_index < 150:
            air_quality = 'Good (80-149)'
        if voc_index < 80:
            air_quality = 'Excellent (<80)'
        
        status_msg = f'{clock_block} - Air: {air_quality} ({voc_index})'
        thingspeak_payload = f'field1={temperature_f}&field2={humidity}&field3={compensated_raw_gas}&field4={voc_index}&status={status_msg}'

        # Initiate MQTT communication
        io.connect(clean_session=True)
        
        # Subscribe to topics (TODO needs to be setup for ThingSpeak)
        # print(f'\nSubscribing: {mqtt_topic}')
        # io.subscribe(mqtt_topic)

        # Poll for incoming messages
        # io.loop()
        
        # Data to publish 
        print(f'\n{THINGSPEAK_TOPIC}\n{thingspeak_payload}\n')
        io.publish(THINGSPEAK_TOPIC, thingspeak_payload, False)

        # Reset next_interval timer
        next_interval = time.monotonic() + write_interval
    
    # Cleanup, memory management.
    del main_group
    gc.collect()
    print('Garbage Collected')
    main_group = displayio.Group()

    # Reset `limit` and `print_stats` variables
    limit += -1
    
    if limit <= 0:
        limit = limit_max
        # print_stats = True
        print('Limits Reset')
        
    time.sleep(1)
