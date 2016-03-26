#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# =====================
#
# Copyright (c) 2016 Artyom Sokolov
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#
# Requires gmusicapi (https://github.com/simon-weber/gmusicapi) and 
# fuzzywuzzy (https://github.com/seatgeek/fuzzywuzzy)

import json
import datetime

from http.client import HTTPSConnection

from gmusicapi import Mobileclient
from fuzzywuzzy import process

DEEZER_ID = 0

GOOGLE_USERNAME = "test@gmail.com"
GOOGLE_PASSWORD = "test"

TEST_RUN = True
LOG_FILE = "expordeezer.log"

# Internal playlist format:
# playlist = { "name": playlist name, "tracks": [ {"artist": artist, 
#                                                  "album":  album,
#                                                  "title":  title }, 
#                                                  "artist": artist_2, 
#                                                  "album":  album_2,
#                                                  "title":  title_2 }, 
#                                                  ... ] }

class Logger:

    FileName = None
    File = None

    def log(prefix, message):
        if Logger.FileName != None and Logger.File == None:
            try:
                Logger.File = open(Logger.FileName, "w", encoding='utf-8')
            except Exception as e:
                Logger.FileName = None
                print("Logger: Can not write log to given file.")

        msg = "{0}: {1}\n".format(prefix, message)

        if Logger.File != None:
            Logger.File.write(msg)
            Logger.File.flush()

        try:
            print(msg, end='')
        except UnicodeEncodeError:
            print("Logger: Can't encode log message. See log file.")

class MusicService:

    def import_playlists(self, playlists):
        raise Exception("Not implemented.")

    def import_playlist(self, playlist):
        raise Exception("Not implemented.")

    def export_playlists(self):
        raise Exception("Not implemented.")


class Deezer(MusicService):

    exportFileName = "deezerPlaylists_{0}.json".format(datetime.datetime.now().strftime("%H_%M_%S"))

    apiVersion = "2.0"
    apiUrl = "api.deezer.com"
    
    def __init__(self, userId):
        self.userId = userId
        self.connection = HTTPSConnection(self.apiUrl)
        self.user = self.get_user()

    def export_playlists_to_file(self, fileName=None):
        if fileName == None:
            if self.exportFileName == None:
                raise Exception("Unknown file name.")
            fileName = self.exportFileName

        with open(fileName, "w") as f:
            json.dump(self.export_playlists(), f)

    def export_playlists(self):
        self.log("Exporting playlists...")

        playlists = self.get_user_playlists()
        exported = []

        for playlist in playlists["data"]:
            self.log("Exporting \"{0}\" playlist.".format(playlist["title"]))

            ans = input("Do you want to export this playlist? (Y/N) ").lower()
            if ans != 'y':
                self.log("Nothing has been exported.")
                continue

            tracksList = self.get_all_playlist_tracks(playlist["id"])

            toExport = {"name": playlist["title"], "tracks": []}
            for track in tracksList:
                toExport["tracks"].append(self.convert_track(track))

            exported.append(toExport)

            self.log("Exported {0} songs.".format(len(tracksList)))

        if len(exported) > 0:
            self.log("Selected playlists exported.")

        return exported

    def log(self, message):
        log("Deezer", message)

    def convert_track(self, deezerApiTrack):
        return { "title":  deezerApiTrack["title"], 
                 "artist": deezerApiTrack["artist"]["name"], 
                 "album":  deezerApiTrack["album"]["title"] }

    def get_all_playlist_tracks(self, playlistId):
        tracks = self.get_tracks(playlistId, 0)
        tracksList = tracks["data"]
        while True:
            if "next" not in tracks:
                break
            tracks = self.get_data(tracks["next"])
            tracksList += tracks["data"]
        return tracksList

    def get_tracks(self, playlistId, offset):
        url = "/{0}/playlist/{1}/tracks?index={2}".format(self.apiVersion, playlistId, offset)
        return self.get_data(url)

    def get_user_playlists(self):
        url = "/{0}/user/{1}/playlists".format(self.apiVersion, self.userId)
        return self.get_data(url)

    def get_playlist(self, playlistId):
        url = "/{0}/playlist/{1}".format(self.apiVersion, playlistId)
        return self.get_data(url)

    def get_user(self):
        url = "/{0}/user/{1}".format(self.apiVersion, self.userId)
        return self.get_data(url)

    def get_data(self, url):
        self.connection.request("GET", url)
        response = self.connection.getresponse()
        responseData = response.read().decode('utf-8')
        return json.loads(responseData)

class GoogleMusic(MusicService):

    storeIdsFileName = "googleMusic_storeIDs_{0}.list".format(datetime.datetime.now().strftime("%H_%M_%S"))

    def __init__(self, username, password):
        self.client = self.auth(username, password)
        if self.client == None:
            raise Exception("Authentication failed. Check credentials.")

    def import_playlists_from_file(self, fileName):
        with open(fileName, "r") as f:
            playlists = json.load(f)
        self.import_playlists(playlists)

    def import_playlists(self, playlists):
        for playlist in playlists:
            self.import_playlist(playlist)

    def import_playlist(self, playlist):
        self.log("Importing playlist \"{0}\"...".format(playlist["name"]))

        importList = []
        for track in playlist["tracks"]:
            searchQuery  = self.format_query(track["artist"], track["title"])
            self.log("Searching for \"{0}\"".format(searchQuery))

            searchResult = self.client.search_all_access(searchQuery)
            if len(searchResult["song_hits"]) == 0:
                self.log("No results for given query.")
                continue

            match = self.find_best_match(searchQuery, searchResult["song_hits"], 75)
            if match == None:
                self.log("Can't find any tracks match query.")
                continue

            self.log("Found match - {0} by {1}".format(match["track"]["title"], match["track"]["artist"]))
            importList.append(match["track"]["storeId"])

        if self.storeIdsFileName != None:
            with open(self.storeIdsFileName, "w") as f:
                for s in importList:
                    f.write(s + "\n")

        if len(importList) > 0 and not TEST_RUN:
            self.log("Importing found matches...")
            playlistId = self.client.create_playlist(playlist["name"])
            self.client.add_songs_to_playlist(playlistId, importList)
            self.log("Successful!")
        else:
            self.log("No matches. Nothing to add.")

    def log(self, msg):
        log("GoogleMusic", msg)

    def format_query(self, artist, title):
        return "{0} {1}".format(artist, title)

    def find_best_match(self, desired, tracks, minRatio):
        if len(tracks) > 0:
            trackNames = [self.format_query(x["track"]["artist"], x["track"]["title"]) for x in tracks]
            match = process.extractOne(desired, trackNames)
            if match[1] > minRatio:
                return tracks[trackNames.index(match[0])]
        return None

    def auth(self, username, password):
        client = Mobileclient(debug_logging=False)
        if client.login(username, password, android_id=Mobileclient.FROM_MAC_ADDRESS):
            return client
        return None


def log(prefix, message):
    Logger.log(prefix, message)

def import_from_deezer_to_GMPAA(deezerid, googlelogin, googlepass):
    deezer = Deezer(deezerid)
    gmusic = GoogleMusic(googlelogin, googlepass)

    deezer.export_playlists_to_file()
    gmusic.import_playlists_from_file(deezer.exportFileName)

def main():
    if LOG_FILE != None:
        Logger.FileName = LOG_FILE

    import_from_deezer_to_GMPAA(DEEZER_ID, GOOGLE_USERNAME, GOOGLE_PASSWORD)


if __name__ == '__main__':
    main()