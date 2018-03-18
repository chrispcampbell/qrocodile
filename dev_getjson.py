#! python3

import argparse
import json
import sys
import os.path
import spotipy
import spotipy.util as util

arg_parser = argparse.ArgumentParser(description='Generates .json files')
arg_parser.add_argument('--input', help='the file containing the list of commands and songs to generate')
arg_parser.add_argument('--spotify-username', help='the username used to set up Spotify access (only needed if you want to generate cards for Spotify tracks)')
args = arg_parser.parse_args()
print(args)

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

def dump_json():
    # Create the output directory in the current path
    dirname = os.getcwd()
    outdir = os.path.join(dirname, 'json_out')
    print(outdir)
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    
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
            (song, album, artist) = process_command(line, index)
        elif line.startswith('spotify:album:'):
            (album, artist) = process_spotify_album(line, index)
        elif line.startswith('spotify:artist:'):
            (artist, album) = process_spotify_artist(line, index)
        elif line.startswith('spotify:track:'):
            (song, album, artist) = process_spotify_track(line, index)
        else:
            print('Failed to handle URI: ' + line)
            exit(1)

def process_spotify_track(uri, index):
    print('def process_spotify_track(uri, index):')
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')

    track = sp.track(uri)

    #print(track)
    print("printing Track here...")

    song = strip_title_junk(track['name'])
    artist = strip_title_junk(track['artists'][0]['name'])
    album = strip_title_junk(track['album']['name'])
    arturl = track['album']['images'][0]['url']
        
    #return (song.encode('utf-8'), album.encode('utf-8'), artist.encode('utf-8'))
    return (song, album, artist) # removed encoding into utf-8 as it turns str into bytes

def process_spotify_artist(uri, index):
    print('def process_spotify_track(uri, index):')
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')

    artist = sp.artist(uri)
    print(artist)

    #song = strip_title_junk(track['name'])
    #artist = strip_title_junk(track['artists'][0]['name'])
    #album = strip_title_junk(track['album']['name'])
    #arturl = track['album']['images'][0]['url']
        
    #return (song.encode('utf-8'), album.encode('utf-8'), artist.encode('utf-8'))
    return (song, album, artist) # removed encoding into utf-8 as it turns str into bytes

def process_spotify_album(uri, index):
    print('def process_spotify_track(uri, index):')
    if not sp:
        raise ValueError('Must configure Spotify API access first using `--spotify-username`')
    
    album = sp.album(uri)
    
    # keeping the strip_title_junk as optional
    #album_name = strip_title_junk(album['name'])
    #artist_name = strip_title_junk(album['artists'][0]['name'])
    album_name = album["name"]
    artist_name = album["artists"][0]["name"]
    print("\n")
    print("Artist: " + artist_name)
    print("Album Name: " + album_name)
    print("Tracks: " + str(album["tracks"]["total"]))
    print("\n")
    # crating and updating the track list
    tracks_all = {}

    # creating and updating the album dict
    album_all = {}
    album_all.update({"Artist": artist_name})
    album_all.update({"Album Name": album_name})

    albumtracks = sp.album_tracks(uri,limit=50,offset=0)
    
    track_list = {}
    tracks_all.update({"Album": {}})
    tracks_all["Album"].update(album_all)
    tracks_all["Album"].update({"Tracks": {}})
    
    for track in albumtracks['items']:
        track_number = track["track_number"]
        track_name = track["name"]
        track_uri = track["uri"]
        print(str(track_number) + ", " + str(track_name) + ", " + str(track_uri))
        track_list.update({track_number: {}})
        track_list[track_number].update({"uri" : track_uri})
        track_list[track_number].update({"name" : track_name})
        tracks_all["Album"]["Tracks"].update(track_list)

    current_path = os.getcwd()
    output_file_tracks = album_name + " tracks"
    output_file_album = album_name
    output_path_tracks = str(current_path + "/json_out/" + output_file_tracks + ".json")
    output_path_tracks_raw = str(current_path + "/json_out/" + output_file_tracks + "_raw.json")
    output_path_album = str(current_path + "/json_out/" + output_file_album + ".json")
    output_path_album_raw = str(current_path + "/json_out/" + output_file_album + "_raw.json")
    
    # creates file <album>.json with the minimal info
    with open(output_path_album,"w") as file:
        json.dump(tracks_all,file,indent=2)
    # creates file <album>_raw.json with all the output of the album:uri
    with open(output_path_album_raw,"w") as file:
        json.dump(album,file,indent=2)
    # creates file <album_tracks>_raw.json with all the output of the album_tracks:uri
    with open(output_path_tracks_raw,"w") as file:
        json.dump(albumtracks,file,indent=2)


    ## node-sonos-http-api ##
    #/RoomName/spotify/now/spotify:track:4LI1ykYGFCcXPWkrpcU7hn
    #/RoomName/spotify/next/spotify:track:4LI1ykYGFCcXPWkrpcU7hn
    #/RoomName/spotify/queue/spotify:track:4LI1ykYGFCcXPWkrpcU7hn
        
    #return (song.encode('utf-8'), album.encode('utf-8'), artist.encode('utf-8'))
    #return (song, album, artist) # removed encoding into utf-8 as it turns str into bytes
    return (album_name,artist_name)

if args.input:
    dump_json()