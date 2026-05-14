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

from pyworkflow.protocol import params, STEPS_PARALLEL
from pyworkflow.object import String
import pyworkflow.utils as pwutils
from pwem.objects import Movie, SetOfMovies, Acquisition
from pwem.protocols import EMProtocol, ProtImportImages

from empiar.utils import FTPDownloader, readFromEmpiar
from empiar.constants import DATA_FORMATS

EMPIAR_REMOTE_ROOT = '/empiar/world_availability/'
FTP_EBI_AC_UK = 'ftp.ebi.ac.uk'


class EmpiarDownloader(EMProtocol):
    """ Downloads movies from EMPIAR and registers them. """
    """
        Downloads and registers cryo-EM movies from the EMPIAR database.

        AI Generated:

        EMPIAR Downloader (EmpiarDownloader) — User Manual
            Overview

            The EMPIAR Downloader protocol retrieves cryo-EM movie datasets directly
            from the EMPIAR repository and registers them inside the Scipion project
            environment. Its purpose is to simplify access to publicly available
            experimental datasets while preserving the metadata required for further
            image processing workflows.

            In practical cryo-EM workflows, this protocol is commonly used during
            dataset preparation and benchmarking experiments. Researchers can quickly
            import raw movies from EMPIAR entries and immediately integrate them into
            preprocessing pipelines such as motion correction, CTF estimation, or
            particle picking.

            Inputs and Download Configuration

            The protocol requires an EMPIAR entry identifier together with a local
            download directory where the files will be stored. Users can optionally
            limit the number of downloaded files or filter the download by file
            extension in order to retrieve only specific movie formats.

            An optional gain reference can also be included. The gain file may be
            downloaded directly from a remote FTP address or provided locally from an
            existing path. This allows proper detector normalization during later
            preprocessing stages.

            Acquisition Parameters

            Since EMPIAR datasets do not always provide complete acquisition metadata,
            the protocol allows manual definition of microscope parameters such as
            magnification, voltage, spherical aberration, amplitude contrast, and
            electron dose. These parameters are attached to the generated movie set
            and become available for downstream cryo-EM processing.

            Download Workflow

            The protocol first retrieves metadata from the EMPIAR API, including the
            dataset title, sampling rate, file format, and remote directory structure.
            Afterwards, it downloads the gain reference if requested and proceeds to
            retrieve the movie files from the EMPIAR FTP server.

            Downloaded movies are linked into the Scipion project structure and
            automatically registered as a SetOfMovies output. During registration,
            frame ranges, sampling rate, and acquisition information are assigned to
            each imported movie.

            Outputs and Interpretation

            After execution, the protocol generates a SetOfMovies object containing
            all successfully downloaded movies together with their associated metadata.
            If a gain reference was provided, it is linked and assigned to the movie
            set automatically.

            The resulting dataset can then be used directly in standard cryo-EM
            preprocessing workflows inside Scipion.

            Practical Recommendations

            For routine usage, it is recommended to verify that the selected EMPIAR
            entry contains the expected movie format before starting large downloads.
            Using extension filters can significantly reduce download time and storage
            requirements when datasets contain auxiliary files.

            When testing workflows or benchmarking pipelines, downloading only a
            subset of movies is often sufficient and can accelerate exploratory
            analyses. For production workflows, ensuring correct acquisition metadata
            and gain references is important for obtaining reliable downstream
            processing results.

            Final Perspective

            The EMPIAR Downloader protocol provides an efficient bridge between the
            EMPIAR public archive and Scipion processing environments. By automating
            dataset retrieval, metadata registration, and movie integration, it
            simplifies the preparation of cryo-EM datasets for reproducible and
            scalable image processing workflows.
        """
    _label = 'empiar downloader'
    _possibleOutputs = {"outputMovies": SetOfMovies}
    stepsExecutionMode = STEPS_PARALLEL

    # -------------------------- DEFINE param functions -----------------------
    def _defineParams(self, form):
        form.addSection("Entry")

        form.addParam("entryId", params.StringParam,
                      label="EMPIAR identifier",
                      default="10200",
                      help="EMPIAR's entry identifier",
                      important=True)

        form.addParam("downloadFolder", params.FolderParam,
                      label="Download folder", important=True,
                      help="Local folder to store downloaded files")

        form.addParam("amountOfImages", params.IntParam,
                      label="Number of files", default=1,
                      help="Number of files to download")

        form.addParam("filterByExt", params.StringParam,
                      label="Filter by extension", default="",
                      help="Enter comma separated extensions to filter files "
                           "that will be downloaded. By default, only the "
                           "movies that match the entry's data format "
                           "will be downloaded.")

        form.addParam("makeEntryFolder", params.BooleanParam,
                      expertLevel=params.LEVEL_ADVANCED,
                      label="Make an entry folder", default=True,
                      help="If activated it will create a subfolder under "
                           "the 'Download folder' with the EMPIAR##### name")

        form.addParam('downloadGain', params.BooleanParam,
                      label="Download gain file?", default=True,
                      help="Leave this empty if not required.")

        form.addParam("gainUrl", params.StringParam,
                      condition="downloadGain",
                      label="Gain reference url",
                      help="URL of the ftp site where the gain image is")

        form.addParam("gainPath", params.FileParam,
                      allowsNull=True,
                      condition="not downloadGain",
                      label="Gain reference path")

        form.addSection("Acquisition")
        ProtImportImages._defineAcquisitionParams(self, form)

        line = form.addLine('Dose (e/A^2)',
                            help="Initial accumulated dose (usually 0) and "
                                 "dose per frame. ")

        line.addParam('doseInitial', params.FloatParam, default=0,
                      label='Initial')

        line.addParam('dosePerFrame', params.FloatParam, default=None,
                      allowsNull=True,
                      label='Per frame')

        form.addParallelSection(threads=3, mpi=0)

    def _acquisitionWizardCondition(self):
        """ Used from define Acquisition param. For this case wizard is not available."""
        return 'False'

    def _insertAllSteps(self):
        readXmlStepId = self._insertFunctionStep(self.readEmpiarMetadataStep,
                                                 prerequisites=[])

        stepDeps = [readXmlStepId]

        if self.downloadGain:
            gainStepId = self._insertFunctionStep(self.downloadGainStep,
                                              prerequisites=[])
            stepDeps.append(gainStepId)

        downloadStepId = self._insertFunctionStep(self.downloadImagesStep,
                                                  prerequisites=stepDeps)
        self._insertFunctionStep(self.closeOutput,
                                 prerequisites=[downloadStepId])

    # --------------------------- STEPS functions -----------------------------
    def readEmpiarMetadataStep(self):
        """ Get some data from the empiar API. """
        title, samplingRate, dataFormat, directory = readFromEmpiar(self.entryId.get())

        # Store returned values as "persistent" attributes
        self.title = String(title)
        self.samplingRate = String(samplingRate)
        self.dataFormat = String(dataFormat)
        self.empiarDirectory = String(directory)

        self._store()

    def downloadGainStep(self):
        """ Downloads the gain file from the URL or use the local file. """

        if self.downloadGain and self.gainUrl.hasValue():
            # Url will probably be a full url...
            # Example: http://ftp.ebi.ac.uk/empiar/world_availability/10200/data/Movies/CountRef_26_000_Oct04_16.13.54.mrc

            # Compose the remote file, without the server part -->
            # /empiar/world_availability/10200/data/Movies/CountRef_26_000_Oct04_16.13.54.mrc
            remoteFile = self.gainUrl.get().split(FTP_EBI_AC_UK)[1]

            # get right part after the entry id and the slash -->
            # data/Movies/CountRef_26_000_Oct04_16.13.54.mrc
            downloadFolder = os.path.dirname(remoteFile.split(self.entryId.get() + "/")[1])
            downloadFolder = os.path.join(self._getRootDownloadFolder(), downloadFolder)

            downloader = FTPDownloader(FTP_EBI_AC_UK)
            downloader.downloadFile(remoteFile, downloadFolder,
                                    fileReadyCallback=self.gainDownloaded)

        elif self.gainPath.get() and os.path.exists(self.gainPath.get()):
            self.gainDownloaded(self.gainPath.get())

    def downloadImagesStep(self):
        """ Make the download happen in the tmp folder of the protocol
        and the final folder to be the extra folder. """
        empiarFolder = self._getEntryRootFolder()
        downloadFolder = self._getRootDownloadFolder()
        downloadFolder = os.path.join(downloadFolder, self.empiarDirectory.get())
        pwutils.makePath(downloadFolder)

        directory = EMPIAR_REMOTE_ROOT + empiarFolder
        filter = self._getDownloadFilter()
        self.info(f"Filter by extension: {filter}")
        ftpDownloader = FTPDownloader(FTP_EBI_AC_UK, fnFilter=filter)
        ftpDownloader.downloadFolder(directory, downloadFolder, self.registerImage,
                                     limit=self.amountOfImages.get())

    def closeOutput(self):
        self.outputMovies.setStreamState(SetOfMovies.STREAM_CLOSED)
        self.outputMovies.write()
        self._store()

    # --------------------------- INFO functions ------------------------------
    def _summary(self):
        summary = []

        summary.append(f"ENTRY: {self.entryId}")
        if hasattr(self, "title"):
            summary.append(f"Title: {self.title}")
            summary.append(f"Sampling rate: {self.samplingRate}")
            summary.append(f"Data format: {self.dataFormat}")
            summary.append(f"Data at: {self.empiarDirectory}")

        return summary

    # -------------------------- UTILS functions ------------------------------
    def gainDownloaded(self, gainfile):
        # Create a link
        dest = self._getExtraPath(os.path.basename(gainfile))
        pwutils.createLink(gainfile, dest)

        outputset = self._getMoviesOutputSet()
        outputset.setGain(dest)
        outputset.write()

        self._store(outputset)

    def _getDownloadFilter(self):
        """ Returns a list of extensions to be matched or None"""
        filter = DATA_FORMATS.get(self.dataFormat.get(), [])
        if self.filterByExt.get() != "":
            exts = self.filterByExt.get().strip().split(",")
            filter.extend(exts)

        return list(set(filter))

    def _getRootDownloadFolder(self):
        if self.makeEntryFolder:
            return os.path.join(self.downloadFolder.get(), "EMPIAR" + self.entryId.get())
        else:
            return self.downloadFolder.get()

    def _getEntryRootFolder(self):
        return os.path.join(self.entryId.get(), self.empiarDirectory.get())

    def registerImage(self, file):
        """ Register a movie taking into account a file path. """
        if pwutils.getExt(file) not in DATA_FORMATS.get(self.dataFormat.get()):
            return  # skip non-movie files

        # Create a link
        dest = self._getExtraPath(os.path.basename(file))
        pwutils.createLink(file, dest)

        newImage = Movie(location=dest)
        dim = newImage.getDim()
        framesRange = [1, dim[2], 1]
        newImage.setFramesRange(framesRange)
        newImage.setSamplingRate(self.samplingRate.get())
        newImage.setMicName(os.path.basename(dest))

        outputset = self._getMoviesOutputSet()
        outputset.append(newImage)
        outputset.write()

        self._store(outputset)

    def _getMoviesOutputSet(self):
        """ Returns the output set; if not available create an empty one. """
        if not hasattr(self, 'outputMovies'):
            outputSet = SetOfMovies.create(self._getPath())
            outputSet.setSamplingRate(self.samplingRate.get())
            outputSet.setStreamState(SetOfMovies.STREAM_OPEN)

            # NOTE: Since acquisition is not described in EMPIAR
            # we go for default values, but we might need params
            acquisition = Acquisition(magnification=self.magnification.get(),
                                      voltage=self.voltage.get(),
                                      sphericalAberration=self.sphericalAberration.get(),
                                      amplitudeContrast=self.amplitudeContrast.get(),
                                      doseInitial=self.doseInitial.get(),
                                      dosePerFrame=self.dosePerFrame.get())
            outputSet.setAcquisition(acquisition)
            self._defineOutputs(outputMovies=outputSet)

        return self.outputMovies
