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

# TODO: Replace with the IP address of the machine running `node-sonos-http-api`
base_url = 'http://10.0.1.6:5005'
# TODO: Replace with the name of your default device/room
current_device = 'Dining Room'
song_only = True
build_queue = False
last_qrcode = ''


# Start the QR code reader
p = os.popen('/usr/bin/zbarcam --prescale=300x200', 'r')


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
    global song_only
    global build_queue

    print('HANDLING COMMAND: ' + qrcode)

    if qrcode == 'cmd:turntable':
        # XXX: Our turntable is hooked up in the dining room, so we always want to
        # source it from that room and play back to the current device; figure out
        # a better way to configure this so it's not hardcoded
        perform_room_request('linein/Dining%%20Room')
        speak = 'I\'ve activated the turntable'
    elif qrcode == 'cmd:livingroom':
        current_device = 'Living Room'
        speak = 'I\'m switching to the living room'
    elif qrcode == 'cmd:diningandkitchen':
        current_device = 'Dining Room'
        speak = 'I\'m switching to the dining room'
    elif qrcode == 'cmd:songonly':
        song_only = True
        speak = 'I\'ll play only the song shown on each card'
    elif qrcode == 'cmd:wholealbum':
        song_only = False
        speak = 'I\'ll play the whole album shown on each card'
    elif qrcode == 'cmd:playnow':
        build_queue = False
        if song_only:
            speak = 'I\'ll play songs as soon as you show them to me'
        else:
            speak = 'I\'ll play albums as soon as you show them to me'
    elif qrcode == 'cmd:buildqueue':
        build_queue = True
        perform_room_request('clearqueue')
        speak = 'I\'ll keep adding songs to the queue'
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

    if build_queue:
        if song_only:
            action = 'queuesongfromhash'
        else:
            action = 'queuealbumfromhash'
    else:
        if song_only:
            action = 'playsongfromhash'
        else:
            action = 'playalbumfromhash'

    perform_room_request('musicsearch/library/{0}/{1}'.format(action, qrcode))


def handle_spotify_item(uri):
    print('PLAYING FROM SPOTIFY: ' + uri)

    if build_queue:
        # TODO: If !song_only, enqueue the album this song comes from
        perform_room_request('spotify/queue/' + uri)
    else:
        # TODO: If !song_only, play the album this song comes from
        perform_room_request('spotify/now/' + uri)


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


# Preload library on startup (it takes a few seconds to prepare the cache)
perform_room_request('musicsearch/library/load')


# Monitor the output of the QR code scanner
def start_scan():
    global p
    while True:
        data = p.readline()
        qrcode = str(data)[8:]
        if qrcode:
            qrcode = qrcode.rstrip()
            handle_qrcode(qrcode)

try:
    start_scan()
except KeyboardInterrupt:
    print('Stop scanning')
finally:
    p.close()
