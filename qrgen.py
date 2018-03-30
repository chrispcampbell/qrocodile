#! python3

import argparse
import hashlib
import json
import os.path
import shutil
import spotipy
import spotipy.util as util
import subprocess
import sys
import requests  # replaces urllib & urllib2
import pyqrcode  # https://pypi.python.org/pypi/PyQRCode replaces system qrencode

# Build a map of the known commands and pictures of their cards
commands = json.load(open('command_cards.txt'))

# Parse the command line arguments
arg_parser = argparse.ArgumentParser(description='Generates an HTML page containing cards with embedded QR codes that can be interpreted by `qrplay`.')
arg_parser.add_argument('--input', help='the file containing the list of commands and songs to generate')
arg_parser.add_argument('--generate-images', action='store_true', help='generate an individual PNG image for each card')
arg_parser.add_argument('--list-library', action='store_true', help='list all available library tracks')
arg_parser.add_argument('--hostname', default='localhost', help='the hostname or IP address of the machine running `node-sonos-http-api`')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
arg_parser.add_argument('--zones', action='store_true', help='generate cards for all available Sonos Zones')
arg_parser.add_argument('--commands', action='store_true', help='generate cards for all commands defined in commands_cards.txt')
args = arg_parser.parse_args()
print(args)

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

def perform_request(url,type):
    response = requests.get(url)
    if type == "txt":
    	result = response.text
    elif type == "json":
    	result = response.json()
    else:
    	result = response.text
    return result

def get_zones():
    rooms_json=perform_request(base_url + '/zones','json')
    
    current_path = os.getcwd()
    output_file_zones = "zones"
    output_path_zones = str(current_path + "/json_out/" + output_file_zones + "_raw.json")
        
    # create a list with all available rooms
    sonoszonesavail=[] #list
    sonoszonesavail_dict={} #dict
    # we need to populate the dict with
    ## room name
    ## art url
    sonosarturl = 'https://raw.githubusercontent.com/google/material-design-icons/master/av/drawable-xxxhdpi/ic_volume_up_black_48dp.png'
    sonosarturl = 'https://d21buns5ku92am.cloudfront.net/61071/images/181023-sonos-logo-black-b45ff7-original-1443493203.png'
    
    for n,val in enumerate(rooms_json):
        sonoszonesavail_dict.update({n: ()}) # creating a tuple
        sonoszonesavail.append(rooms_json[n]['coordinator']['roomName'])
    print("\nList of Zones: ", sonoszonesavail,"\n")
    
    # copy cards.css to /out folder
    shutil.copyfile('cards.css', 'out/cards.css')
    shutil.copyfile('sonos_360.png', 'out/sonos_360.png')

    # Begin the HTML template
    html = '''
        <html>
        <head>
        <link rel="stylesheet" href="cards.css">
        </head>
        <body>
        '''

    for n in sonoszonesavail:
        qrout = 'out/'+n+'_qr.png'
        artout = 'out/'+n+'_art.jpg'
        qrimg = n+'_qr.png'
        artimg = n+'_art.jpg'
        qr = pyqrcode.create("changezone:"+n)
        qr.png(qrout, scale=6)
        qr.show()
        # the sonos logo will be one we keep locally or downloaded from github once
        #print(subprocess.check_output(['curl', sonosarturl, '-o', artout]))
        # generate html
        html += '<div class="card">\n'
        #html += '  <img src="'+artimg+'" class="art"/>\n'.format(artout)
        html += '  <img src="sonos_360.png" class="art"/>\n'.format(artout)
        html += '  <img src="'+qrimg+'" class="qrcode"/>\n'.format(qrout)
        html += '  <div class="labels">\n'
        html += '    <p class="zone">'+n+'</p>\n'#.format(song)
        html += '  </div>\n'
        html += '</div>\n'

    html += '</body>\n'
    html += '</html>\n'

    with open('out/zones.html', 'w') as f:
        f.write(html)


def list_library_tracks(): #not used/doesn't work
    result_json = perform_request(base_url + '/musicsearch/library/listall','text')
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


def process_command(uri, index):  # new function using the outside json file
    cmdname = commands[uri]['command']
    arturl = commands[uri]['image']

    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)

    qr1 = pyqrcode.create(uri)
    qr1.png(qrout, scale=6)
    qr1.show()

    print(subprocess.check_output(['curl', arturl, '-o', artout]))
    return (cmdname, None, None)
        
    
def process_spotify_track(uri, index):
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')

    track = sp.track(uri)

    print(track["name"])
    # print('track    : ' + track['name'])
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
    qr1 = pyqrcode.create(uri)
    qr1.png(qrout, scale=6)
    qr1.show()

    # Fetch the artwork and save to the output directory
    print(subprocess.check_output(['curl', arturl, '-o', artout]))
    
    return (song, album, artist) # removed encoding into utf-8 as it turns str into bytes

def process_spotify_album(uri, index):
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')

    album = sp.album(uri)

    print(album['name'])
    # print('track    : ' + track['name'])
    # print 'artist   : ' + track['artists'][0]['name']
    # print 'album    : ' + track['album']['name']
    # print 'cover art: ' + track['album']['images'][0]['url']

    # keeping the strip_title_junk as optional
    #album_name = strip_title_junk(album['name'])
    #artist_name = strip_title_junk(album['artists'][0]['name'])
    album_name = album["name"]
    artist_name = album["artists"][0]["name"]
    arturl = album['images'][0]['url']
    
    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)
    
    # Create a QR code from the album URI
    qr1 = pyqrcode.create(uri)
    qr1.png(qrout, scale=6)
    qr1.show()

    # Fetch the artwork and save to the output directory
    print(subprocess.check_output(['curl', arturl, '-o', artout]))
    
    album_blank = ""
    return (album_name, album_blank, artist_name) # removed encoding into utf-8 as it turns str into bytes

def process_spotify_playlist(uri, index):
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')
    
    sp_user = uri.split(":")[2]
    playlist = sp.user_playlist(sp_user,uri)
    playlist_name = playlist["name"]

    # keeping the strip_title_junk as optional
    #album_name = strip_title_junk(album['name'])
    #artist_name = strip_title_junk(album['artists'][0]['name'])
    playlist_owner = playlist["owner"]["id"]
    arturl = playlist['images'][0]['url']
    
    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)
    
    # Create a QR code from the album URI
    qr1 = pyqrcode.create(uri)
    qr1.png(qrout, scale=6)
    qr1.show()

    # Fetch the artwork and save to the output directory
    print(subprocess.check_output(['curl', arturl, '-o', artout]))
    
    playlist_blank = ""
    return (playlist_name, playlist_owner, playlist_blank) # removed encoding into utf-8 as it turns str into bytes


def process_library_track(uri, index):
    track_json = perform_request(base_url + '/musicsearch/library/metadata/' + uri,'txt')
    track = json.loads(track_json)
    #print(track)

    song = strip_title_junk(track['trackName'])
    artist = strip_title_junk(track['artistName'])
    album = strip_title_junk(track['albumName'])
    arturl = track['artworkUrl']

    # XXX: Sonos strips the "The" prefix for bands that start with "The" (it appears to do this
    # only in listing contexts; when querying the current/next queue track it still includes
    # the "The").  As a dumb hack (to preserve the "The") we can look at the raw URI for the
    # track (this assumes an iTunes-style directory structure), parse out the artist directory
    # name and see if it starts with "The".
    from urlparse import urlparse
    uri_parts = urlparse(track['uri'])
    uri_path = uri_parts.path

    (uri_path, song_part) = os.path.split(uri_path)
    (uri_path, album_part) = os.path.split(uri_path)
    (uri_path, artist_part) = os.path.split(uri_path)
    if artist_part.startswith('The%20'):
        artist = 'The ' + artist

    # Determine the output image file names
    qrout = 'out/{0}qr.png'.format(index)
    artout = 'out/{0}art.jpg'.format(index)

    # Create a QR code from the track URI
    qr1 = pyqrcode.create(uri)
    qr1.png(qrout, scale=6)
    qr1.show()

    # Fetch the artwork and save to the output directory
    print(subprocess.check_output(['curl', arturl, '-o', artout]))
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
# DISABLED
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
    ## disabled conversion of HTML to PNG
    ##png_filename = 'out/{0}'.format(index)
    ##print(subprocess.check_output(['webkit2png', html_filename, '--scale=1.0', '--clipped', '--clipwidth=720', '--clipheight=640', '-o', png_filename]))

    # Rename the file to remove the extra `-clipped` suffix that `webkit2png` includes by default
    ##os.rename(png_filename + '-clipped.png', png_filename + 'card.png')


def generate_cards():
    # Create the output directory
    dirname = os.getcwd()
    outdir = os.path.join(dirname, 'out')
    print(outdir)
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    # Read the file containing the list of commands and songs to generate

    if args.input:
        with open(args.input) as f:
            lines = f.readlines()
    elif args.commands:
        lines=[]
        for command in commands:
            lines.append(commands[command]['command'])

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
        elif line.startswith('spotify:album:'):
            (song, album, artist) = process_spotify_album(line, index)
        elif line.startswith('spotify:track:'):
            (song, album, artist) = process_spotify_track(line, index)
        #elif line.startswith('spotify:user:',':playlist:'):
        elif line.startswith('spotify:user:'):
            if (":playlist:") in line:
                (song, album, artist) = process_spotify_playlist(line, index)
        elif line.startswith('lib:'):
            (song, album, artist) = process_library_track(line, index)
        else:
            print('Failed to handle URI: ' + line)
            exit(1)

        # Append the HTML for this card
        if album == "":
            html += '<div class="card">\n'
            html += card_content_html(index, artist, album, song)
            html += '</div>\n'
        else:
            html += '<div class="card">\n'
            html += card_content_html(index, artist, album, song)
            html += '</div>\n'
        

        if args.generate_images:
            # Also generate an individual PNG for the card
            generate_individual_card_image(index, artist, album, song)

        if args.zones:
            generate_individual_card_image(index, artist, album, song)

        if index % 2 == 1:
            html += '<br style="clear: both;"/>\n'

        index += 1

    html += '</body>\n'
    html += '</html>\n'

    if args.commands:
        with open('out/commands.html', 'w') as f:
            f.write(html)
    else:
        with open('out/index.html', 'w') as f:
            f.write(html)

if args.input:
    generate_cards()
elif args.list_library:
    list_library_tracks()
elif args.zones:
    get_zones()
elif args.commands:
    generate_cards()