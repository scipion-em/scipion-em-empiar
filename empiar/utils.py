# **************************************************************************
# *
# * Authors:     Pablo Conesa (pconesa@cnb.csic.es)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************

import os
import json
import requests
import ftplib

import pyworkflow.utils as pwutils


def readFromEmpiar(entryId):
    """ Access a specific dataset from EMPIAR repository.
    :param entryId: Entry ID
    """
    empiarUrl = 'https://www.ebi.ac.uk/empiar/api/entry/' + entryId  # URL of EMPIAR API

    jsonFile = requests.get(empiarUrl, allow_redirects=True)               # getting the json file
    content = json.loads(jsonFile.content.decode('utf-8'))                 # extract the json content
    empiarName = 'EMPIAR-' + entryId                                       # dataset name

    # correspondingAuthor = content[empiarName]['corresponding_author']    # dataset author
    # organization = correspondingAuthor['author']['organization']         # authors organization
    # depositionDate = content[empiarName]['deposition_date']              # dataset deposition date
    title = content[empiarName]['title']                                   # dataset title

    # Image set metadata
    imageSets = content[empiarName]['imagesets']                           # dataset images information

    # Find movie sets
    movieSets = [i for i in imageSets if i['category'] == "micrographs - multiframe"]

    if not movieSets:
        raise FileNotFoundError(f"EMPIAR entry {entryId} does not have any movies!")
    else:
        print(f"Found {len(movieSets)} datasets from EMPIAR entry "
              f"{entryId}. Will download the first one only!")

    samplingRate = movieSets[0]['pixel_width']                # images sampling rate
    dataFormat = movieSets[0]['data_format']                  # images format
    directory = movieSets[0]['directory']
    # releaseDate = content[empiarName]['release_date']                    # dataset release date
    # datasetSize = content[empiarName]['dataset_size']                    # dataset size

    # You may want to return more elements
    return title, samplingRate, dataFormat, directory


class FTPDownloader:
    """ Downloads files from an FTP server with a limit, a filter
    and a callback called on each downloaded file"""
    def __init__(self, server, username='anonymous', password='', fnFilter=None):
        self.server = server
        self.username = username
        self.password = password
        self.ftp_client = None
        self.download_count = 0
        self.filter = fnFilter

    def _getFtp(self):
        if not self.ftp_client:
            # Establish the connection
            ftp = ftplib.FTP(self.server)
            ftp.login(self.username, self.password)
            self.ftp_client = ftp

        return self.ftp_client

    def downloadFile(self, remoteFile, downloadFolder, fileReadyCallback=None):
        """ Downloads a single file into a local folder"""
        remoteFolder = os.path.dirname(remoteFile)

        # Change to the proper directory
        ftp = self._getFtp()
        ftp.cwd(remoteFolder)

        # Create local folder if it does not exist
        pwutils.makePath(downloadFolder)

        # Download the file
        self._downloadFile(os.path.basename(remoteFile), downloadFolder,
                           fileReadyCallback=fileReadyCallback)

        ftp.close()

    def downloadFolder(self, remoteFolder, downloadFolder, fileReadyCallback=None, limit=None):
        """ Downloads files recursively from a remote folder until limit is reached"""

        # Change to the proper directory
        ftp = self._getFtp()
        ftp.cwd(remoteFolder)
        self.download_count = 0

        self._downloadFiles(downloadFolder, fileReadyCallback, limit)

        ftp.close()

    def matchFilter(self, file):
        if self.filter is None:
            return True
        else:
            # Assume extensions --> endswith. There are files uploaded as .tif.jpg!!
            for pattern in self.filter:
                if file.endswith(pattern):
                    return True
        return False

    def _downloadFiles(self, downloadFolder, fileReadyCallback=None, limit=None):
        print(f"Downloading files to {downloadFolder}")
        pwutils.makePath(downloadFolder)

        # For each file/folder
        for filename in self.ftp_client.nlst():
            if self.isFolder(filename):
                self._downloadFiles(os.path.join(downloadFolder, filename),
                                    fileReadyCallback, limit=limit)
            else:
                if self.matchFilter(filename):
                    self._downloadFile(filename, downloadFolder, fileReadyCallback)
                else:
                    print(f"Skipping {filename}")

            if limit and limit == self.download_count:
                print(f"File limit of {limit} reached!")
                return

    def isFolder(self, folder):
        try:
            self.ftp_client.cwd(folder)
            return True
        except ftplib.error_perm:
            return False

    def _downloadFile(self, file, downloadFolder, fileReadyCallback=None):
        """ Downloads a single file using current ftp status (cwd)"""
        finalPath = os.path.join(downloadFolder, file)
        if os.path.exists(finalPath):
            # TODO: more robust check in case local file is partially downloaded..
            #  size?.
            #  Download with a suffix?
            print(f"{finalPath} exists. Skipping download.")
            fileReadyCallback(finalPath)
            self.download_count += 1
            return

        # Start actual downloading
        fhandle = open(finalPath, 'wb')
        print(pwutils.yellowStr(f"Downloading: {finalPath}"), flush=True)

        bytesDownloaded = 0
        SIZE_100MB = 1024*1024*100
        nextPrint = SIZE_100MB

        def downloadListener(chunk):
            nonlocal nextPrint
            nonlocal bytesDownloaded

            # Chunks are not constant!!
            bytesDownloaded += len(chunk)

            fhandle.write(chunk)

            # Print every 100 MB
            if bytesDownloaded >= nextPrint:
                print(pwutils.prettySize(bytesDownloaded), end="\r", flush=True)
                nextPrint += SIZE_100MB

        self.ftp_client.retrbinary('RETR ' + file, downloadListener)
        fhandle.close()
        self.download_count += 1

        # Call the callback..
        if fileReadyCallback:
            fileReadyCallback(finalPath)
