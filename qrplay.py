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

import json
import os
import sys
import urllib
import urllib2

# Set to `True` to execute a series of commands listed in `debug.txt`
DEBUG = False

# TODO: Replace with the IP address of the machine running `node-sonos-http-api`
base_url = 'http://10.0.1.6:5005'
# TODO: Replace with the name of your default device/room
current_device = 'Dining Room'
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


def perform_room_request(path):
    qdevice = urllib.quote(current_device)
    perform_request(base_url + '/' + qdevice + '/' + path)


def handle_command(qrcode):
    global current_device
    global current_mode

    print('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:turntable':
        # XXX: Our turntable is hooked up in the dining room, so we always want to
        # source it from that room and play back to the current device; figure out
        # a better way to configure this so it's not hardcoded
        perform_room_request('linein/Dining%20Room')
        speak = 'I\'ve activated the turntable'
    elif qrcode == 'cmd:livingroom':
        current_device = 'Living Room'
        speak = 'I\'m switching to the living room'
    elif qrcode == 'cmd:diningandkitchen':
        current_device = 'Dining Room'
        speak = 'I\'m switching to the dining room'
    elif qrcode == 'cmd:songonly':
        current_mode = Mode.PLAY_SONG_IMMEDIATELY
        speak = 'Show me a card and I\'ll play that song right away'
    elif qrcode == 'cmd:wholealbum':
        current_mode = Mode.PLAY_ALBUM_IMMEDIATELY
        speak = 'Show me a card and I\'ll play the whole album'
    elif qrcode == 'cmd:buildqueue':
        current_mode = Mode.BUILD_QUEUE
        perform_room_request('clearqueue')
        speak = 'Show me a card and I\'ll add that song to the list'
    elif qrcode == 'cmd:whatsong':
        perform_room_request('saysong')
        return
    else:
        speak = 'Hmm, I don\'t recognize that command'

    perform_room_request('say/' + urllib.quote(speak))


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

    # Ignore redundant codes, except for cases like "whatsong", where you might
    # want to hear it multiple times
    if qrcode == last_qrcode and qrcode != 'cmd:whatsong':
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


if len(sys.argv) <= 1 or sys.argv[1] != 'noload':
    # Preload library on startup (it takes a few seconds to prepare the cache)
    print('Please wait, server is indexing the library...')
    perform_room_request('musicsearch/library/load')
    print('Indexing complete!')



# Monitor the output of the QR code scanner
def start_scan():
    while True:
        data = p.readline()
        qrcode = str(data)[8:]
        if qrcode:
            qrcode = qrcode.rstrip()
            handle_qrcode(qrcode)


def read_debug_script():
    from time import sleep

    # Read codes from `debug.txt`
    with open('debug.txt') as f:
        debug_codes = f.readlines()

    # Handle each code followed by a short delay
    for code in debug_codes:
        # Remove any trailing comments and newline (and ignore any empty or comment-only lines)
        code = code.split("#")[0]
        code = code.strip()
        if code:
            handle_qrcode(code)
            sleep(4)


if DEBUG:
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
