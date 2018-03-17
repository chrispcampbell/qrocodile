#! python3

import argparse
import json
import sys
import os.path
import spotipy
import spotipy.util as util
import requests

arg_parser = argparse.ArgumentParser(description='Generates .json files')
arg_parser.add_argument('--input', help='the file containing the list of commands and songs to generate')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
arg_parser.add_argument('--default-device', default='Living Room', help='the name of your default device/room')
arg_parser.add_argument('--hostname', default='192.168.188.14', help='the hostname or IP address of the machine running `node-sonos-http-api`')
args = arg_parser.parse_args()
print(args)

if not args.hostname:
    hostname = "192.168.188.14"
    base_url = 'http://' + hostname + ':5005'
else:
    base_url = 'http://' + args.hostname + ':5005'

# Login to Spotify
if args.spotify_username:
    scope = 'user-library-read'
    token = util.prompt_for_user_token(args.spotify_username, scope)
    if token:
        sp = spotipy.Spotify(auth=token)
    else:
        raise ValueError('Can\'t get Spotify token for ' + username)
else:
    sp = None

# Load the most recently used device, if available, otherwise fall back on the `default-device` argument
try:
    with open('.last-device', 'r') as device_file:
        current_device = device_file.read().replace('\n', '')
        print('Defaulting to last used room: ' + current_device)
except:
    current_device = args.default_device
    print('Initial room: ' + current_device)


def perform_request(url):
    print(url)
    response = requests.get(url) # equivalent to urllib2.urlopen(url)
    result = response.text # equivalent to urllib2.read()
    print(result)

def perform_room_request(path):
    qdevice=current_device.replace(" ", "%20")
    if " " in current_device:
        qdevice=current_device.replace(" ", "%20")
    else:
        qdevice=current_device
    perform_request(base_url + '/' + qdevice + '/' + path)



def dump_json():    
    # Read the file containing the list of uris
    with open(args.input) as f:
        lines = f.readlines()

    # The index of the current item being processed
    index = 0

    for line in lines:
        # Trim newline
        line = line.strip()

        # Remove any trailing comments and newline (and ignore any empty or comment-only lines)
        line = line.split('#')[0]
        line = line.strip()
        if not line:
            continue

        if line.startswith('cmd:'):
            process_command(line, index)
        elif line.startswith('spotify:album:'):
            handle_spotify_album(line)
        elif line.startswith('spotify:artist:'):
            handle_spotify_artist(line, index)
        elif line.startswith('spotify:track:'):
            handle_spotify_track(line, index)
        else:
            print('Failed to handle URI: ' + line)
            exit(1)

def handle_spotify_album(uri):    
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

if args.input:
    dump_json()