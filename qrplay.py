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
import sys
import urllib
import urllib2

# Parse the command line arguments
arg_parser = argparse.ArgumentParser(description='Translates QR codes detected by a camera into Sonos commands.')
arg_parser.add_argument('--default-device', default='Dining Room', help='the name of your default device/room')
arg_parser.add_argument('--linein-source', default='Dining Room', help='the name of the device/room used as the line-in source')
arg_parser.add_argument('--hostname', default='localhost', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--skip-load', action='store_true', help='skip loading of the music library (useful if the server has already loaded it)')
arg_parser.add_argument('--debug-file', help='read commands from a file instead of launching scanner')
args = arg_parser.parse_args()
print args


base_url = 'http://' + args.hostname + ':5005'

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
    response = urllib2.urlopen(url)
    result = response.read()
    print(result)


def perform_global_request(path):
    perform_request(base_url + '/' + path)


def perform_room_request(path):
    qdevice = urllib.quote(current_device)
    perform_request(base_url + '/' + qdevice + '/' + path)


def switch_to_room(room):
    perform_global_request('pauseall')
    current_device = room
    with open(".last-device", "w") as device_file:
        device_file.write(current_device)


def speak(phrase):
    print('SPEAKING: \'{0}\''.format(phrase))
    perform_room_request('say/' + urllib.quote(phrase))


def handle_command(qrcode):
    global current_device
    global current_mode

    print('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:playpause':
        perform_room_request('playpause')
        phrase = None
    elif qrcode == 'cmd:next':
        perform_room_request('next')
        phrase = None
    elif qrcode == 'cmd:turntable':
        perform_room_request('linein/' + urllib.quote(args.linein_source))
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
        perform_room_request('pause')
        perform_room_request('clearqueue')
        phrase = 'Show me a card and I\'ll add that song to the list'
    elif qrcode == 'cmd:whatsong':
        perform_room_request('saysong')
        phrase = None
    elif qrcode == 'cmd:whatnext':
        perform_room_request('saynext')
        phrase = None
    else:
        phrase = 'Hmm, I don\'t recognize that command'

    if phrase:
        speak(phrase)


def handle_library_item(qrcode):
    if not qrcode.startswith('lib:'):
        return

    print('PLAYING FROM LIBRARY: ' + qrcode)

    if current_mode == Mode.BUILD_QUEUE:
        action = 'queuesongfromhash'
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        action = 'playalbumfromhash'
    else:
        action = 'playsongfromhash'

    perform_room_request('musicsearch/library/{0}/{1}'.format(action, qrcode))


def handle_spotify_item(uri):
    print('PLAYING FROM SPOTIFY: ' + uri)

    if current_mode == Mode.BUILD_QUEUE:
        perform_room_request('spotify/queue/' + uri)
    elif current_mode == Mode.PLAY_ALBUM_IMMEDIATELY:
        perform_room_request('spotify/clearqueueandplayalbum/' + uri)
    else:
        perform_room_request('spotify/clearqueueandplaysong/' + uri)


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
    elif qrcode.startswith('spotify:'):
        handle_spotify_item(qrcode)
    else:
        handle_library_item(qrcode)
        
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
    from time import sleep

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
    p = os.popen('/usr/bin/zbarcam --prescale=300x200', 'r')
    try:
        start_scan()
    except KeyboardInterrupt:
        print('Stopping scanner...')
    finally:
        p.close()
