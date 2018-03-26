#! python3
#
# Copyright (c) 2018 Chris Campbell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import argparse
import json
import os
import subprocess
import sys
from time import sleep
import requests  # replaces urllib & urllib2
import spotipy
import spotipy.util as util

# Parse the command line arguments
arg_parser = argparse.ArgumentParser(description='Translates QR codes detected by a camera into Sonos commands.')
arg_parser.add_argument('--default-device', default='Living Room', help='the name of your default device/room')
arg_parser.add_argument('--linein-source', default='Living Room', help='the name of the device/room used as the line-in source')
arg_parser.add_argument('--hostname', default='192.168.188.14', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--skip-load', action='store_true', help='skip loading of the music library (useful if the server has already loaded it)')
arg_parser.add_argument('--debug-file', help='read commands from a file instead of launching scanner')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
args = arg_parser.parse_args()
print(args)

# setting base_url used to access sonos-http-api
base_url = 'http://' + args.hostname + ':5005'

# setting output of stdout
import sys
sys.stdout = open('qrplay.log', 'w')

if args.spotify_username:
    # Set up Spotify access (comment this out if you don't want to generate cards for Spotify tracks)
    scope = 'user-library-read'
    token = util.prompt_for_user_token(args.spotify_username, scope)
    if token:
        sp = spotipy.Spotify(auth=token)
    else:
        raise ValueError('Can\'t get Spotify token for ' + username)
else:
    # No Spotify
    sp = None


# Load the most recently used device, if available, otherwise fall back on the `default-device` argument
try:
    with open('.last-device', 'r') as device_file:
        current_device = device_file.read().replace('\n', '')
        print('Defaulting to last used room: ' + current_device)
except:
    current_device = args.default_device
    print('Initial room: ' + current_device)

# Keep track of the last-seen code
last_qrcode = ''


class Mode:
    PLAY_SONG_IMMEDIATELY = 1
    PLAY_ALBUM_IMMEDIATELY = 2
    BUILD_QUEUE = 3

current_mode = Mode.PLAY_SONG_IMMEDIATELY


def perform_request(url):
    print(url)
    response = requests.get(url) # equivalent to urllib2.urlopen(url)
    result = response.text # equivalent to urllib2.read()
    print(result)


def perform_global_request(path):
    perform_request(base_url + '/' + path)


def perform_room_request(path):
    #qdevice = urllib.quote(current_device)
    #qdevice=current_device # requests should take care of the decoding
    if " " in current_device:
        qdevice=current_device.replace(" ", "%20")
    else:
        qdevice=current_device
    perform_request(base_url + '/' + qdevice + '/' + path)


def switch_to_room(room):
    global current_device

    perform_global_request('pauseall')
    current_device = room
    with open(".last-device", "w") as device_file:
        device_file.write(current_device)


def speak(phrase):
    print('SPEAKING: \'{0}\''.format(phrase))
    #perform_room_request('say/' + urllib.quote(phrase))
    perform_room_request('say/' + phrase)


# Causes the onboard green LED to blink on and off twice.  (This assumes Raspberry Pi 3 Model B; your
# mileage may vary.)
def blink_led():
    duration = 0.15

    def led_off():
	#subprocess.call("echo 0 > /sys/class/leds/led0/brightness", shell=True)
        subprocess.call("echo 1 | sudo tee /sys/class/leds/led0/brightness", shell=True)

    def led_on():
        #subprocess.call("echo 1 > /sys/class/leds/led0/brightness", shell=True)
        subprocess.call("echo 0 | sudo tee /sys/class/leds/led0/brightness", shell=True)

    # Technically we only need to do this once when the script launches
    #subprocess.call("echo none > /sys/class/leds/led0/trigger", shell=True)
    subprocess.call("echo none | tee /sys/class/leds/led0/trigger", shell=True)


    led_on()
    sleep(duration)
    led_off()
    sleep(duration)
    led_on()
    sleep(duration)
    led_off()


def handle_command(qrcode):
    global current_mode

    print('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:playpause':
        perform_room_request('playpause')
        phrase = None
    elif qrcode == 'cmd:next':
        perform_room_request('next')
        phrase = None
    elif qrcode == 'cmd:turntable':
        #perform_room_request('linein/' + urllib.quote(args.linein_source))
        perform_room_request('linein/' + args.linein_source)
        perform_room_request('play')
        phrase = 'I\'ve activated the turntable'
    elif qrcode == 'cmd:livingroom':
        switch_to_room('Living Room')
        phrase = 'I\'m switching to the living room'
    elif qrcode == 'cmd:diningandkitchen':
        switch_to_room('Dining Room')
        phrase = 'I\'m switching to the dining room'
    elif qrcode == 'cmd:songonly':
        current_mode = Mode.PLAY_SONG_IMMEDIATELY
        phrase = 'Show me a card and I\'ll play that song right away'
    elif qrcode == 'cmd:wholealbum':
        current_mode = Mode.PLAY_ALBUM_IMMEDIATELY
        phrase = 'Show me a card and I\'ll play the whole album'
    elif qrcode == 'cmd:buildqueue':
        current_mode = Mode.BUILD_QUEUE
        #perform_room_request('pause')
        perform_room_request('clearqueue')
        phrase = 'Let\'s build a list of songs'
    elif qrcode == 'cmd:whatsong':
        perform_room_request('saysong')
        phrase = None
    elif qrcode.startswith('changezone:'):
        newroom = qrcode.split(":")[1]
        switch_to_room(newroom)
        phrase = 'I\'m switching to the ' + newroom
    elif qrcode == 'cmd:whatnext':
        perform_room_request('saynext')
        phrase = None
    else:
        phrase = 'Hmm, I don\'t recognize that command'

    if phrase:
        speak(phrase)


def handle_library_item(uri):
    if not uri.startswith('lib:'):
        return

    print('PLAYING FROM LIBRARY: ' + uri)

    if current_mode == Mode.BUILD_QUEUE:
        action = 'queuesongfromhash'
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        action = 'playalbumfromhash'
    else:
        action = 'playsongfromhash'

    perform_room_request('musicsearch/library/{0}/{1}'.format(action, uri))


def handle_spotify_item(uri):
    print('PLAYING FROM SPOTIFY: ' + uri)

    if current_mode == Mode.BUILD_QUEUE:
        action = 'queue'
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        #action = 'clearqueueandplayalbum'
        action = 'now'  # using 'now' as I could not find command clearqueueandplayalbum
    else:
        #action = 'clearqueueandplaysong'
        action = 'now'  # using 'now' as I could not find command clearqueueandplayalbum

    perform_room_request('spotify/{0}/{1}'.format(action, uri))

def handle_spotify_album(uri):
    print('PLAYING ALBUM FROM SPOTIFY: ' + uri)
    
    album_raw = sp.album(uri)
    album_name = album_raw["name"]
    artist_name = album_raw["artists"][0]["name"]

    # crating and updating the track list   
    album_tracks_raw = sp.album_tracks(uri,limit=50,offset=0)
    album_tracks = {}

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))
        
    for track in album_tracks_raw['items']:
        track_number = track["track_number"]
        track_name = track["name"]
        track_uri = track["uri"]
        album_tracks.update({track_number: {}})
        album_tracks[track_number].update({"uri" : track_uri})
        album_tracks[track_number].update({"name" : track_name})
        print(track_number)
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
            #action = 'play'
            #perform_room_request('{0}'.format(action))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))

def handle_spotify_playlist(uri):
    print('PLAYING PLAYLIST FROM SPOTIFY: ' + uri)
    uri = 'spotify:user:dernorbs:playlist:4ZVegZjqOHdLvaSYFDo4c7'
    sp_user = uri.split(":")[2]
    playlist_raw = sp.user_playlist(sp_user,uri)
    playlist_name = playlist_raw["name"]

    # images
    # playlist_raw['images']

    # creating and updating the track list   
    playlist_tracks_raw = sp.user_playlist_tracks(uri,limit=50,offset=0)
    playlist_tracks = {}

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))
        
    for track in playlist_raw['tracks']:
        track_number = track["track_number"]
        track_name = track["name"]
        track_uri = track["uri"]
        playlist_tracks.update({track_number: {}})
        playlist_tracks[track_number].update({"uri" : track_uri})
        playlist_tracks[track_number].update({"name" : track_name})
        print(track_number)
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
            #action = 'play'
            #perform_room_request('{0}'.format(action))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))


def handle_qrcode(qrcode):
    global last_qrcode

    # Ignore redundant codes, except for commands like "whatsong", where you might
    # want to perform it multiple times
    if qrcode == last_qrcode and not qrcode.startswith('cmd:'):
        print('IGNORING REDUNDANT QRCODE: ' + qrcode)
        return

    print('HANDLING QRCODE: ' + qrcode)

    if qrcode.startswith('cmd:'):
        handle_command(qrcode)
    elif qrcode.startswith('spotify:album:'):
        # CONCEPT = OK!
        handle_spotify_album(qrcode)
    elif qrcode.startswith('spotify:artist:'):
        # NOT READY
        handle_spotify_artist(qrcode)
    elif qrcode.startswith('spotify:user:'):
        if (":playlist:") in qrcode:
            handle_spotify_playlist(qrcode)
    elif qrcode.startswith('spotify:'):
        handle_spotify_item(qrcode)
    else:
        handle_library_item(qrcode)

    # Blink the onboard LED to give some visual indication that a code was handled
    # (especially useful for cases where there's no other auditory feedback, like
    # when adding songs to the queue)
    if not args.debug_file:
        blink_led()
        
    last_qrcode = qrcode


# Monitor the output of the QR code scanner.
def start_scan():
    while True:
        data = p.readline()
        qrcode = str(data)[8:]
        if qrcode:
            qrcode = qrcode.rstrip()
            handle_qrcode(qrcode)


# Read from the `debug.txt` file and handle one code at a time.
def read_debug_script():
    # Read codes from `debug.txt`
    with open(args.debug_file) as f:
        debug_codes = f.readlines()

    # Handle each code followed by a short delay
    for code in debug_codes:
        # Remove any trailing comments and newline (and ignore any empty or comment-only lines)
        code = code.split("#")[0]
        code = code.strip()
        if code:
            handle_qrcode(code)
            sleep(4)


perform_global_request('pauseall')
speak('Hello, I\'m qrocodile.')

if not args.skip_load:
    # Preload library on startup (it takes a few seconds to prepare the cache)
    print('Indexing the library...')
    speak('Please give me a moment to gather my thoughts.')
    perform_room_request('musicsearch/library/loadifneeded')
    print('Indexing complete!')
    speak('I\'m ready now!')

speak('Show me a card!')

if args.debug_file:
    # Run through a list of codes from a local file
    read_debug_script()
else:
    # Start the QR code reader
    ## --nodisplay required as running pi headless
    ## had the error "spawning input thread: Invalid argument (22)"
    p = os.popen('/usr/bin/zbarcam --nodisplay --prescale=300x200', 'r')
    try:
        start_scan()
    except KeyboardInterrupt:
        print('Stopping scanner...')
    finally:
        p.close()
