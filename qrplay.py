#!/usr/bin/env python3
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

import logging
import argparse
import json
import os
import subprocess
import sys
from time import sleep
import requests  # replaces urllib & urllib2
import spotipy
import spotipy.util as util

# setting up logfile qrplay.log
LOG_FORMAT = "%(levelname)s %(asctime)s - %(message)s"
current_path = os.getcwd()
output_file_defaults = os.path.join(current_path,"qrplay.log")
logging.basicConfig(filename = output_file_defaults, 
                    filemode = "w",
                    level = logging.INFO,
                    format = LOG_FORMAT)
logger = logging.getLogger()

def check_node_sonos_http_api():
    """ function to check if port 5005 is available
    ... and if not, change my_defaults file to use localhost"""
    import socket
    global default_hostname
    port = 5005
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex((default_hostname,port))
    if result == 0:
        logger.info("port is open")
    else:
        default_hostname = '127.0.0.1'
        print("Port is not open")
        logger.info("Port is not open")
        print("setting default_hostname to localhost")
        logger.info("setting default_hostname to localhost")
        defaults = {} # dict
        defaults.update({"default_spotify_user": default_spotify_user })
        defaults.update({"default_hostname" : default_hostname})
        defaults.update({"default_room" : default_room})
        current_path = os.getcwd()
        output_file_defaults = os.path.join(current_path,"my_defaults.txt")
        file = open(output_file_defaults, 'w')
        json.dump(defaults,file,indent=2)
        file.close()
    s.close()

def load_defaults():
    # loading defaults from my_defaults.txt
    current_path = os.getcwd()
    defaults = json.load(open("my_defaults.txt", "r"))
    global default_room
    global default_spotify_user
    global default_hostname
    default_room=defaults['default_room']
    default_spotify_user = defaults['default_spotify_user']
    default_hostname = defaults['default_hostname']
    check_node_sonos_http_api()
    #logger.info("imported defaults: " + str(defaults))
    return(default_room,default_spotify_user,default_hostname)

load_defaults()

# Parse the command line arguments
# removed all the default= arguments as I'd like to use the contents of the my_defaults.txt file
arg_parser = argparse.ArgumentParser(description='Translates QR codes detected by a camera into Sonos commands.')
arg_parser.add_argument('--default-device', help='the name of your default device/room')
arg_parser.add_argument('--linein-source', help='the name of the device/room used as the line-in source')
arg_parser.add_argument('--hostname', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--skip-load', action='store_true', help='skip loading of the music library (useful if the server has already loaded it)')
arg_parser.add_argument('--debug-file', help='read commands from a file instead of launching scanner')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
args = arg_parser.parse_args()
print('Args=' + str(args))

# setting base_url used to access sonos-http-api
if args.hostname:
    base_url = 'http://' + args.hostname + ':5005'
else:
    base_url = 'http://' + default_hostname + ':5005'

# setting the language code and volume for announcements
announcementlang = "en-gb" # see https://github.com/chrispcampbell/node-sonos-http-api/tree/qrocodile
# 40 is way too loud
announcementvolume = 10

# Load the most recently used device, if available, otherwise fall back on the `default-device` argument
try:
    with open('.last-device', 'r') as device_file:
        current_device = device_file.read().replace('\n', '')
        logger.info('Defaulting to last used room: ' + current_device)
except:
    #current_device = defaults['default_room']
    #current_device = args.default_device
    current_device = default_room
    logger.info('Initial room: ' + current_device)

# Keep track of the last-seen code
last_qrcode = ''

class Mode:
    PLAY_SONG_IMMEDIATELY = 1
    PLAY_ALBUM_IMMEDIATELY = 2
    BUILD_QUEUE = 3

current_mode = Mode.PLAY_SONG_IMMEDIATELY


def perform_request(url,type):
    # as with qrgen, this function has been expanded
    # to support two kinds of output: text and json, the latter turned into usable dicts
    logger.info("url= " + str(url))
    response = requests.get(url)
    if type == "txt":
    	result = response.text
    elif type == "json":
    	result = response.json()
    else:
    	result = response.text
    #print(result)
    return result


def perform_global_request(path):
    perform_request(base_url + '/' + path,None)


def perform_room_request(path):
    #qdevice = urllib.quote(current_device)
    #qdevice=current_device # requests should take care of the decoding
    if " " in current_device:
        qdevice=current_device.replace(" ", "%20")
    else:
        qdevice=current_device
    #perform_request(base_url + '/' + qdevice + '/' + path,None)
    response = perform_request(base_url + '/' + qdevice + '/' + path,'json')
    return response

def switch_to_room(room):
    global current_device
    #perform_global_request('pauseall')
    current_device = room
    with open(".last-device", "w") as device_file:
        device_file.write(current_device)


def speak(phrase):
    logger.info('SPEAKING: \'{0}\''.format(phrase))
    #setting language to en-gb and level 
    perform_room_request('say/' + str(phrase) + "/"+ str(announcementlang) + "/" + str(announcementvolume))


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

    logger.info('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:turntable':
        perform_room_request('linein/' + args.linein_source)
        perform_room_request('play')
        phrase = 'I\'ve activated the turntable',10
    elif qrcode.startswith('changezone:'):
        newroom = qrcode.split(":")[1]
        logger.info('Switching to '+ newroom)
        switch_to_room(newroom)
        phrase = 'Switching to ' + newroom,10
    elif qrcode.startswith('cmd:'):
        action = qrcode.split(":")[1]
        perform_room_request(action)
        phrase = None
    # no cards printed out for these
    #elif qrcode == 'mode:songonly':
    #    current_mode = Mode.PLAY_SONG_IMMEDIATELY
    #    phrase = 'Show me a card and I\'ll play that song right away'
    #elif qrcode == 'mode:wholealbum':
    #    current_mode = Mode.PLAY_ALBUM_IMMEDIATELY
    #    phrase = 'Show me a card and I\'ll play the whole album'
    elif qrcode == 'mode:buildqueue':
        current_mode = Mode.BUILD_QUEUE
        perform_room_request('clearqueue')
        phrase = 'Let\'s build a list of songs'
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
    logger.info('PLAYING FROM SPOTIFY: ' + uri)

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
    logger.info('PLAYING ALBUM FROM SPOTIFY: ' + uri + '\n')
    
    album_raw = sp.album(uri)
    album_name = album_raw["name"]
    artist_name = album_raw["artists"][0]["name"]

    # crating and updating the track list   
    album_tracks_raw = sp.album_tracks(uri,limit=50,offset=0)
    album_tracks = {}

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))

    # turning off shuffle before starting the new queue
    action = 'shuffle/off'
    perform_room_request('{0}'.format(action))
            
    for track in album_tracks_raw['items']:
        track_number = track["track_number"]
        track_name = track["name"]
        track_uri = track["uri"]
        album_tracks.update({track_number: {}})
        album_tracks[track_number].update({"uri" : track_uri})
        album_tracks[track_number].update({"name" : track_name})
        print(str(track_number) + ": " + str(track_name))
        logger.info(str(track_number) + ": " + str(track_name))
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))

def handle_spotify_playlist(uri):
    logger.info('PLAYING PLAYLIST FROM SPOTIFY: ' + uri + '\n')
    sp_user = uri.split(":")[2]
    playlist_raw = sp.user_playlist(sp_user,uri)
    playlist_name = playlist_raw["name"]

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))

    # creating and updating the track list   
    playlist_tracks_raw = sp.user_playlist_tracks(sp_user,uri,limit=50,offset=0)
    playlist_tracks = {}
    # turning off shuffle before starting the new queue
    action = 'shuffle/off'
    perform_room_request('{0}'.format(action))
    # when not able to add a track to the queue, spotipy resets the track # to 1
    # in this case I just handled the track nr separately with n
    n = 0
    for track in playlist_tracks_raw['items']:
        n = n + 1
        #track_number = track['track']['track_number'] # disabled as causing issues with non-playable tracks
        track_number = n
        track_name = track['track']["name"]
        track_uri = track['track']["uri"]
        playlist_tracks.update({track_number: {}})
        playlist_tracks[track_number].update({"uri" : track_uri})
        playlist_tracks[track_number].update({"name" : track_name})
        print(str(track_number) + ": " + str(track_name))
        logger.info(str(track_number) + ": " + str(track_name))
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))

def handle_spotify_artist(uri):
    logger.info('PLAYING ARTIST FROM SPOTIFY: ' + uri + '\n')
    artist_raw = sp.artist(uri)
    artist_name = artist_raw["name"]

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))

    # getting top tracks and in order to avoid "cannot play track", set the country
    ## https://spotipy.readthedocs.io/en/latest/#spotipy.client.Spotify.artist_top_tracks
    artist_top_tracks = sp.artist_top_tracks(uri,country='DE')
    
    # plan is to get a collection of songs from all albums based on:
    ## https://spotipy.readthedocs.io/en/latest/#spotipy.client.Spotify.artist_albums

    artist_tracks = {}

    # turning on shuffle before starting the new queue
    action = 'shuffle/on'
    perform_room_request('{0}'.format(action))
    # when not able to add a track to the queue, spotipy resets the track # to 1
    # in this case I just handled the track nr separately with n
    n = 0
    for track in artist_top_tracks['tracks']:
        n = n + 1
        track_number = n
        track_name = track["name"]
        track_uri = track["uri"]
        artist_tracks.update({track_number: {}})
        artist_tracks[track_number].update({"uri" : track_uri})
        artist_tracks[track_number].update({"name" : track_name})
        print(str(track_number) + ": " + str(track_name))
        logger.info(str(track_number) + ": " + str(track_name))
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))

def handle_spotify_artist(uri):
    artist_raw = sp.artist(uri)
    artist_name = artist_raw["name"]

    # clear the sonos queue
    action = 'clearqueue'
    perform_room_request('{0}'.format(action))

    # getting top tracks and in order to avoid "cannot play track", set the country
    ## https://spotipy.readthedocs.io/en/latest/#spotipy.client.Spotify.artist_top_tracks
    artist_top_tracks = sp.artist_top_tracks(uri,country='DE')
    
    # plan is to get a collection of songs from all albums based on:
    ## https://spotipy.readthedocs.io/en/latest/#spotipy.client.Spotify.artist_albums

    artist_tracks = {}

    # turning on shuffle before starting the new queue
    action = 'shuffle/on'
    perform_room_request('{0}'.format(action))
    # when not able to add a track to the queue, spotipy resets the track # to 1
    # in this case I just handled the track nr separately with n
    n = 0
    for track in artist_top_tracks['tracks']:
        n = n + 1
        track_number = n
        track_name = track["name"]
        track_uri = track["uri"]
        artist_tracks.update({track_number: {}})
        artist_tracks[track_number].update({"uri" : track_uri})
        artist_tracks[track_number].update({"name" : track_name})
        print(str(track_number) + ": " + str(track_name))
        if track_number == int("1"):
            # play track 1 immediately
            action = 'now'
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))
        else:
            # add all remaining tracks to queue
            action = "queue"
            perform_room_request('spotify/{0}/{1}'.format(action, str(track_uri)))

def handle_qrcode(qrcode):
    logger.info("Handling qrcode: " + str(qrcode))
    global last_qrcode

    # Ignore redundant codes, except for commands like "whatsong", where you might
    # want to perform it multiple times
    if qrcode == last_qrcode and not qrcode.startswith('cmd:'):
        print('IGNORING REDUNDANT QRCODE: ' + qrcode)
        return

    print('HANDLING QRCODE: ' + qrcode)

    if qrcode.startswith('cmd:'):
        handle_command(qrcode)
    elif qrcode.startswith('mode:'):
        handle_command(qrcode)
    elif qrcode.startswith('spotify:album:'):
        handle_spotify_album(qrcode)
    elif qrcode.startswith('spotify:artist:'):
        handle_spotify_artist(qrcode)
    elif qrcode.startswith('spotify:user:'):
        if (":playlist:") in qrcode:
            handle_spotify_playlist(qrcode)
    elif qrcode.startswith('spotify:'):
        handle_spotify_item(qrcode)
    elif qrcode.startswith('changezone:'):
        handle_command(qrcode)
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
            logger.info("Scanned qrcode: " + str(qrcode))
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


if args.debug_file:
    # Run through a list of codes from a local file
    read_debug_script()
elif args.spotify_username:
    # Set up Spotify access (comment this out if you don't want to generate cards for Spotify tracks)
    scope = 'user-library-read'
    token = util.prompt_for_user_token(args.spotify_username, scope)
    #token = util.prompt_for_user_token(spotify_username, scope)
    if token:
        sp = spotipy.Spotify(auth=token)
        logger.info("logged into Spotify")
    else:
        raise ValueError('Can\'t get Spotify token for ' + username)
        logger.info('Can\'t get Spotify token for ' + username)
        sp = None
        logger.info('Not using a Spotify account')
else:
    # Set up Spotify access (comment this out if you don't want to generate cards for Spotify tracks)
    scope = 'user-library-read'
    token = util.prompt_for_user_token(default_spotify_user, scope)
    if token:
        sp = spotipy.Spotify(auth=token)
        logger.info("logged into Spotify")
    else:
        raise ValueError('Can\'t get Spotify token for ' + username)
        logger.info('Can\'t get Spotify token for ' + username)
        sp = None
        logger.info('Not using a Spotify account')

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
    #load_defaults()
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
