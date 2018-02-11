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
import hashlib
import json
import os.path
import shutil
import spotipy
import spotipy.util as util
import subprocess
import sys
import urllib
import urllib2

# Build a map of the known commands
# TODO: Might be better to specify these in the input file to allow for more customization
# (instead of hardcoding names/images here)
commands = {
  'cmd:playpause': ('Play / Pause', 'https://raw.githubusercontent.com/google/material-design-icons/master/av/drawable-xxxhdpi/ic_pause_circle_outline_black_48dp.png'),
  'cmd:next': ('Skip to Next Song', 'https://raw.githubusercontent.com/google/material-design-icons/master/av/drawable-xxxhdpi/ic_skip_next_black_48dp.png'),
  'cmd:turntable': ('Turntable', 'http://moziru.com/images/record-player-clipart-vector-3.jpg'),
  'cmd:livingroom': ('Living Room', 'http://icons.iconarchive.com/icons/icons8/ios7/512/Household-Livingroom-icon.png'),
  'cmd:diningandkitchen': ('Dining Room / Kitchen', 'https://png.icons8.com/ios/540//dining-room.png'),
  'cmd:songonly': ('Play the Song Only', 'https://raw.githubusercontent.com/google/material-design-icons/master/image/drawable-xxxhdpi/ic_audiotrack_black_48dp.png'),
  'cmd:wholealbum': ('Play the Whole Album', 'https://raw.githubusercontent.com/google/material-design-icons/master/av/drawable-xxxhdpi/ic_album_black_48dp.png'),
  'cmd:buildqueue': ('Build List of Songs', 'https://raw.githubusercontent.com/google/material-design-icons/master/av/drawable-xxxhdpi/ic_playlist_add_black_48dp.png'),
  'cmd:whatsong': ('What\'s Playing?', 'https://raw.githubusercontent.com/google/material-design-icons/master/action/drawable-xxxhdpi/ic_help_outline_black_48dp.png'),
  'cmd:whatnext': ('What\'s Next?', 'https://raw.githubusercontent.com/google/material-design-icons/master/action/drawable-xxxhdpi/ic_help_outline_black_48dp.png')
}

# Parse the command line arguments
arg_parser = argparse.ArgumentParser(description='Generates an HTML page containing cards with embedded QR codes that can be interpreted by `qrplay`.')
arg_parser.add_argument('--input', help='the file containing the list of commands and songs to generate')
arg_parser.add_argument('--generate-images', action='store_true', help='generate an individual PNG image for each card')
arg_parser.add_argument('--list-library', action='store_true', help='list all available library tracks')
arg_parser.add_argument('--hostname', default='localhost', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
args = arg_parser.parse_args()
print args

base_url = 'http://' + args.hostname + ':5005'

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


def perform_request(url):
    print(url)
    response = urllib2.urlopen(url)
    result = response.read()
    return result


def list_library_tracks():
    result_json = perform_request(base_url + '/musicsearch/library/listall')
    tracks = json.loads(result_json)['tracks']
    for t in tracks:
        print(t)


# Removes extra junk from titles, e.g:
#   (Original Motion Picture Soundtrack)
#   - From <Movie>
#   (Remastered & Expanded Edition)
def strip_title_junk(title):
    junk = [' (Original', ' - From', ' (Remaster', ' [Remaster']
    for j in junk:
        index = title.find(j)
        if index >= 0:
            return title[:index]
    return title


def process_command(uri, index):
    (cmdname, arturl) = commands[uri]
    
    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)
    
    # Create a QR code from the command URI
    print subprocess.check_output(['qrencode', '-o', qrout, uri])

    # Fetch the artwork and save to the output directory
    print subprocess.check_output(['curl', arturl, '-o', artout])

    return (cmdname, None, None)
    
    
def process_spotify_track(uri, index):
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')

    track = sp.track(uri)

    print track
    # print 'track    : ' + track['name']
    # print 'artist   : ' + track['artists'][0]['name']
    # print 'album    : ' + track['album']['name']
    # print 'cover art: ' + track['album']['images'][0]['url']
    
    song = strip_title_junk(track['name'])
    artist = strip_title_junk(track['artists'][0]['name'])
    album = strip_title_junk(track['album']['name'])
    arturl = track['album']['images'][0]['url']
    
    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)
    
    # Create a QR code from the track URI
    print subprocess.check_output(['qrencode', '-o', qrout, uri])

    # Fetch the artwork and save to the output directory
    print subprocess.check_output(['curl', arturl, '-o', artout])

    return (song.encode('utf-8'), album.encode('utf-8'), artist.encode('utf-8'))


def process_library_track(uri, index):
    track_json = perform_request(base_url + '/musicsearch/library/metadata/' + uri)
    track = json.loads(track_json)
    print(track)

    song = strip_title_junk(track['trackName'])
    artist = strip_title_junk(track['artistName'])
    album = strip_title_junk(track['albumName'])
    arturl = track['artworkUrl']

    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)

    # Create a QR code from the track URI
    print subprocess.check_output(['qrencode', '-o', qrout, uri])

    # Fetch the artwork and save to the output directory
    print subprocess.check_output(['curl', arturl, '-o', artout])

    return (song.encode('utf-8'), album.encode('utf-8'), artist.encode('utf-8'))


# Return the HTML content for a single card.
def card_content_html(index, artist, album, song):
    qrimg = '{0}qr.png'.format(index)
    artimg = '{0}art.jpg'.format(index)

    html = ''
    html += '  <img src="{0}" class="art"/>\n'.format(artimg)
    html += '  <img src="{0}" class="qrcode"/>\n'.format(qrimg)
    html += '  <div class="labels">\n'
    html += '    <p class="song">{0}</p>\n'.format(song)
    if artist:
        html += '    <p class="artist"><span class="small">by</span> {0}</p>\n'.format(artist)
    if album:
        html += '    <p class="album"><span class="small">from</span> {0}</p>\n'.format(album)
    html += '  </div>\n'
    return html


# Generate a PNG version of an individual card (with no dashed lines).
def generate_individual_card_image(index, artist, album, song):
    # First generate an HTML file containing the individual card
    html = ''
    html += '<html>\n'
    html += '<head>\n'
    html += ' <link rel="stylesheet" href="cards.css">\n'
    html += '</head>\n'
    html += '<body>\n'

    html += '<div class="singlecard">\n'
    html += card_content_html(index, artist, album, song)
    html += '</div>\n'

    html += '</body>\n'
    html += '</html>\n'

    html_filename = 'out/{0}.html'.format(index)
    with open(html_filename, 'w') as f:
        f.write(html)

    # Then convert the HTML to a PNG image (beware the hardcoded values; these need to align
    # with the dimensions in `cards.css`)
    png_filename = 'out/{0}'.format(index)
    print subprocess.check_output(['webkit2png', html_filename, '--scale=1.0', '--clipped', '--clipwidth=720', '--clipheight=640', '-o', png_filename])

    # Rename the file to remove the extra `-clipped` suffix that `webkit2png` includes by default
    os.rename(png_filename + '-clipped.png', png_filename + 'card.png')


def generate_cards():
    # Create the output directory
    dirname = os.getcwd()
    outdir = os.path.join(dirname, 'out')
    print(outdir)
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.mkdir(outdir)

    # Read the file containing the list of commands and songs to generate
    with open(args.input) as f:
        lines = f.readlines()

    # The index of the current item being processed
    index = 0

    # Copy the CSS file into the output directory.  (Note the use of 'page-break-inside: avoid'
    # in `cards.css`; this prevents the card divs from being spread across multiple pages
    # when printed.)
    shutil.copyfile('cards.css', 'out/cards.css')

    # Begin the HTML template
    html = '''
<html>
<head>
  <link rel="stylesheet" href="cards.css">
</head>
<body>
'''

    for line in lines:
        # Trim newline
        line = line.strip()

        # Remove any trailing comments and newline (and ignore any empty or comment-only lines)
        line = line.split('#')[0]
        line = line.strip()
        if not line:
            continue

        if line.startswith('cmd:'):
            (song, album, artist) = process_command(line, index)
        elif line.startswith('spotify:'):
            (song, album, artist) = process_spotify_track(line, index)
        elif line.startswith('lib:'):
            (song, album, artist) = process_library_track(line, index)
        else:
            print('Failed to handle URI: ' + line)
            exit(1)

        # Append the HTML for this card
        html += '<div class="card">\n'
        html += card_content_html(index, artist, album, song)
        html += '</div>\n'

        if args.generate_images:
            # Also generate an individual PNG for the card
            generate_individual_card_image(index, artist, album, song)

        if index % 2 == 1:
            html += '<br style="clear: both;"/>\n'

        index += 1

    html += '</body>\n'
    html += '</html>\n'

    print(html)

    with open('out/index.html', 'w') as f:
        f.write(html)


if args.input:
    generate_cards()
elif args.list_library:
    list_library_tracks()
