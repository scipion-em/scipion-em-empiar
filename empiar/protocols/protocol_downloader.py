import json
import requests
import ftplib
import os

from pwem.objects import Movie, SetOfMovies, Acquisition
from pwem.protocols import EMProtocol
from pyworkflow.protocol import params, String, STEPS_PARALLEL
import pyworkflow.utils as pwutils

EMPIAR_REMOTE_ROOT = '/empiar/world_availability/'

FTP_EBI_AC_UK = 'ftp.ebi.ac.uk'


class EmpiarDownloader(EMProtocol):
    """
    Downloads movies from EMPIAR and registers them.
    """
    _label = 'empiar downloader'

    dataFormatsToExtensions = {"MRC": ".mrc", "MRCS": ".mrcs",
                               "TIFF": [".tif", ".tiff"],
                               "DM4": ".dm4", "HDF5": [".hdf"]}

    def __init__(self, **args):
        EMProtocol.__init__(self, **args)
        self.stepsExecutionMode = STEPS_PARALLEL  # Defining that the protocol contain parallel steps

    def _defineParams(self, form):
        # add a section
        form.addSection("Entry")

        # add a parameter to capture the EMPIAR entry ID:
        # name --> entryId, String param, default value 10200, you choose the label
        # Ideally we want it in bold is "important", it should not be empty, and fill the help.
        form.addParam("entryId", params.StringParam, label="EMPIAR identifier", default="10200",
                      help="EMPIAR's entry identifier", important=True)
        # add another parameter to set a limit of downloaded files:
        # name-->amountOfImages, Integer param , default to 1, choose the label and the help
        # it has to be positive (use "validators" argument, it expects a list of
        # pyworkflow.protocol.params.Validator, look for the Positive Validator)
        form.addParam("amountOfImages", params.IntParam, label="Number of files", default=1,
                      help="Number of files to download", validators=[params.Positive])

        # Download folder
        form.addParam("downloadFolder", params.FolderParam, label="Download folder", important=True,
                      help="Local folder to store downloaded files")

        form.addParam("makeEntryFolder", params.BooleanParam, label="Make an entry folder", default=True,
                      help="If activated it will create a subfolder under the 'Download folder' with the EMPIAR##### name")

        form.addParam("gainUrl", params.StringParam, label="Gain url", help="Url in the ftp site where the gain image is")

        # Parallel section defining the number of threads and mpi to use
        form.addParallelSection(threads=3, mpi=1)

    def _insertAllSteps(self):
        self.readXmlFile = self._insertFunctionStep(self.readEmpiarMetadataStep)  # read the dataset xml file from EMPIAR
        if self.gainUrl.get():
            self._insertFunctionStep(self.downloadGainStep)
        self.downloadImages = self._insertFunctionStep(self.downloadImagesStep)  # download the movies and register them in parallel
        self.closeSet = self._insertFunctionStep(self.closeOutput)  # close the registered dataset set

    def downloadGainStep(self):
        """ Downloads the gain file from the URL"""

        # Url will probably be a full url...
        # Example: http://ftp.ebi.ac.uk/empiar/world_availability/10200/data/Movies/CountRef_26_000_Oct04_16.13.54.mrc

        # Split by entry id
        gainSplit =self.gainUrl.get().split(FTP_EBI_AC_UK)

        # Compose the remote file, without the server part --> /empiar/world_availability/10200/data/Movies/CountRef_26_000_Oct04_16.13.54.mrc
        remoteFile = gainSplit[1]

        # get right part after the entry id and the slash --> data/Movies/CountRef_26_000_Oct04_16.13.54.mrc
        downloadFolder = os.path.dirname(remoteFile.split(self.entryId.get()+ "/")[1])
        downloadFolder = os.path.join(self._getRootDownloadFolder(), downloadFolder)

        downloader = FTPDownloader(FTP_EBI_AC_UK)

        downloader.downloadFile(remoteFile, downloadFolder, fileReadyCallback=self.gainDownloaded)

    def gainDownloaded(self, gainfile):

        # Create a link
        dest = self._getExtraPath(os.path.basename(gainfile))
        pwutils.createLink(gainfile, dest)
        
        outputset = self._getMoviesOutputSet()
        
        outputset.setGain(dest)

        # In both cases, write the set to the disk. set.write() --> set.sqlite
        outputset.write()

        # Save the protocol with the new  status: protocol._store() --> run.db
        self._store()

    def _getDownloadFilter(self):
        """ Returns a list of extensions to be matched based on EMPIAR dataFormat or None"""

        return self.dataFormatsToExtensions.get(self.dataFormat.get(), None)

    def _getRootDownloadFolder(self):

        if self.makeEntryFolder:
            return os.path.join(self.downloadFolder.get(), "EMPIAR" + self.entryId.get())
        else:
            return self.downloadFolder.get()

    def _getEntryRootFolder(self):
        return "%s/%s" % (self.entryId.get() ,self.empiarDirectory.get())

    def downloadImagesStep(self):
        # Call the method provided below
        # Make the download happen in the tmp folder of the protocol and the final folder to be the extra folder
        empiarFolder = self._getEntryRootFolder()

        downloadFolder = self._getRootDownloadFolder()
        downloadFolder = os.path.join(downloadFolder, self.empiarDirectory.get())

        pwutils.makePath(downloadFolder)

        # Directory information
        directory = EMPIAR_REMOTE_ROOT + empiarFolder

        ftpDownloader = FTPDownloader(FTP_EBI_AC_UK, filter=self._getDownloadFilter())
        ftpDownloader.downloadFolder(directory, downloadFolder, self.registerImage, limit=self.amountOfImages.get())


    def registerImage(self, file):
        """
        Register an image taking into account a file path
        """

        # Create a link
        dest = self._getExtraPath(os.path.basename(file))
        pwutils.createLink(file, dest)

        # Create a Movie object having file as the location: see pwem.objects.data.Movie()
        newImage = Movie(location=dest)

        # Set the frame range
        dim = newImage.getDim()
        range = [1, dim[2], 1]
        newImage.setFramesRange(range)

        # Set the movie sampling rate to the sampling rate obtained in the readXmlFromEmpiar step
        newImage.setSamplingRate(self.samplingRate.get())

        # Mic name!! Important
        newImage.setMicName(os.path.basename(dest))

        # Pass the movie to _addMovieToOutput
        self._addMovieToOutput(newImage)

    def _addMovieToOutput(self, movie):
        """ Adds a movie to the output set"""
        outputset = self._getMoviesOutputSet()

        outputset.append(movie)

        # In both cases, write the set to the disk. set.write() --> set.sqlite
        outputset.write()

        # Save the protocol with the new  status: protocol._store() --> run.db
        self._store()


    def _getMoviesOutputSet(self):
        """
        Returns the output set if not available create an empty one
        """

        # Do we have the attribute "outputMovies"?
        if not hasattr(self, 'outputMovies'):  # the output is defined

            # Create the SetOfMovies using its create(path) method: pass the path of the protocol (hint: self._getPath())
            outputSet = SetOfMovies.create(self._getPath())

            # set the sampling rate: set.setSamplingRate() passing the stored sampling rate from the readXmlFromEmpiarStep
            # NOTE: Scipion objects are wrappers to actual python types. To get the python value use .get() method
            outputSet.setSamplingRate(self.samplingRate.get())

            # set the set's .streamState to open (set.setStreamState). Constant for the state is Set.STREAM_OPEN.
            outputSet.setStreamState(SetOfMovies.STREAM_OPEN)

            # Acquisition: NOTE. Since acquisition is not described in EMPIAR we go for default values but we might need params
            acquisition = Acquisition(magnification=59000, voltage=300, sphericalAberration=2.0, amplitudeContrast=0.1)
            outputSet.setAcquisition(acquisition)

            # define the output in the protocol (_defineOutputs). Be sure you use outputMovies as the name of the output
            self._defineOutputs(outputMovies=outputSet)

        return self.outputMovies
    
    def readEmpiarMetadataStep(self):
        # Call the method provided below to get some data from the empiar xml
        title, samplingRate, dataFormat, directory = readXmlFromEmpiar(self.entryId.get())

        # Store returned values as "persistent" attributes: String, Integer, Float
        self.title = String(title)
        self.samplingRate = String(samplingRate)
        self.dataFormat = String(dataFormat)
        self.empiarDirectory = String(directory)

        # Use _store method to write them
        self._store()

    def closeOutput(self):
        """
        Close the registered set
        """
        # Set the outputMovies streamState using setStreamState method with the value SetOfMovies.STREAM_CLOSED
        self.outputMovies.setStreamState(SetOfMovies.STREAM_CLOSED)

        # Save the outputMovies using the write() method
        self.outputMovies.write()

        # Save the protocol: Hint: _store()
        self._store()

    def _summary(self):
        summary = []

        summary.append("ENTRY: %s" % self.entryId)

        # Check we have the summary attributes (readXmlStep has happened) (HINT: hasattr will do)
        if hasattr(self, "title"):
            # Add items to the summary list like:
            summary.append("Title: %s" % self.title)
            summary.append("Sampling rate: %s" % self.samplingRate)
            summary.append("Data format: %s" % self.dataFormat)
            summary.append("Data at: %s" % self.empiarDirectory)

            # How would you have more values in the summary? (HINT: return more values in readXmlFromEmpiar)

        return summary


# Helper methods #########################################################

def readXmlFromEmpiar(entryId):
        """
        Read the xml file of a specific dataset from EMPIAR repository
        """
        empiarXmlUrl = 'https://www.ebi.ac.uk/pdbe/emdb/empiar/api/entry/' + entryId  # URL of EMPIAR API

        xmlFile = requests.get(empiarXmlUrl, allow_redirects=True)               # getting the xml file
        content = (json.loads(xmlFile.content.decode('utf-8')))                  # extract the xml content
        empiarName = 'EMPIAR-' + entryId                                         # dataset name

        # correspondingAuthor = content[empiarName]['corresponding_author']         # dataset authors
        # organization = String(correspondingAuthor['author']['organization']) # authors organization
        # depositionDate = String(content[empiarName]['deposition_date'])          # dataset deposition date
        title = content[empiarName]['title']                            # dataset title

        # Image set metadata
        imageSets = content[empiarName]['imagesets']                             # dataset images information

        samplingRate = imageSets[0]['pixel_width']                # images sampling rate
        dataFormat = imageSets[0]['data_format']                   # images format

        directory = imageSets[0]['directory']
        category = imageSets[0]['category']

        # releaseDate = String(content[empiarName]['release_date'])                # dataset release date
        # datasetSize = String(content[empiarName]['dataset_size'])                # dataset size
        # empiarName = String(empiarName)

        # You may want to return more elements
        return title, samplingRate, dataFormat, directory


class FTPDownloader:
    """ Downloads files from an FTP server with a limit, a filter and a callback called on each downloaded file"""
    def __init__(self, server, username='anonymous', password='', filter=None):

        self.server = server
        self.username=username
        self.password=password
        self.ftp_client = None
        self.download_count = 0
        self.filter = filter if not isinstance(filter, str) else [filter]

    def _getFtp(self):

        if not self.ftp_client:
            # Establish the connection
            ftp = ftplib.FTP(self.server)
            ftp.login(self.username, self.password)
            self.ftp_client = ftp

        return ftp

    def downloadFile(self, remoteFile, downloadFolder, fileReadyCallback=None):
        """ Downloads a single file into a local folder"""
        remoteFolder = os.path.dirname(remoteFile)

        # Change to the proper directory
        ftp = self._getFtp()
        ftp.cwd(remoteFolder)

        # Create local folder if it does not exists
        pwutils.makePath(downloadFolder)

        # Download the file
        self._downloadFile(os.path.basename(remoteFile), downloadFolder, fileReadyCallback=fileReadyCallback)

        ftp.close()

    def downloadFolder(self, remoteFolder, downloadFolder, fileReadyCallback=None, limit = None):
        """ Downloads files recursively fro a remote folder until limit is reached"""

        # Change to the proper directory
        ftp = self._getFtp()
        ftp.cwd(remoteFolder)
        self.download_count = 0

        self._downloadFiles(downloadFolder, fileReadyCallback, limit)

        ftp.close()

    def matchFilter(self, file):
        if self.filter is None:
            return True
        elif callable(self.filter):
            return self.filter(file)
        else:
            # Assume extensions --> endswith. There are files uploaded as .tif.jpg!!
            for pattern in self.filter:
                if file.endswith(pattern):
                    return True
        return False

    def _downloadFiles(self, downloadFolder, fileReadyCallback=None, limit=None):

        print("Downloading files to %s" % downloadFolder)
        pwutils.makePath(downloadFolder)

        # For each file/folder
        for filename in self.ftp_client.nlst():
            if self.isFolder(filename):
                self._downloadFiles(os.path.join(downloadFolder, filename), fileReadyCallback, limit=limit)
            else:
                if self.matchFilter(filename):
                    self._downloadFile(filename,downloadFolder, fileReadyCallback)
                else:
                    print("File does not match filter: %s" % self.filter)

            if limit and limit == self.download_count:
                return

    def isFolder(self, folder):
        try:
            self.ftp_client.cwd(folder)
            print("Folder %s found. Moved to it." % folder)
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
            print("%s exists. Skipping download." % finalPath)
            fileReadyCallback(finalPath)
            self.download_count += 1
            return

        # Start actual downloading
        fhandle = open(finalPath, 'wb')
        print(pwutils.yellowStr('Getting: ' + finalPath), flush=True)

        bytesDownloaded = 0
        SIZE_10MB = 1024*1024*10
        nextPrint = SIZE_10MB # 10MB

        def downloadListener(chunk):
            nonlocal nextPrint
            nonlocal bytesDownloaded

            # Chunks are not constant!!
            bytesDownloaded += len(chunk)

            fhandle.write(chunk)

            # Print every 1024*10 ch
            if bytesDownloaded >= nextPrint:
                print(pwutils.prettySize(bytesDownloaded), end="\r", flush=True)
                nextPrint += SIZE_10MB

        self.ftp_client.retrbinary('RETR ' + file, downloadListener)
        fhandle.close()
        self.download_count += 1

        # Call the callback..
        if fileReadyCallback:
            fileReadyCallback(finalPath)
