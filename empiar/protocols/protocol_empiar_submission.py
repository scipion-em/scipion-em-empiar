# **************************************************************************
# *
# * Authors:     Yaiza Rancel (cyrancel@cnb.csic.es)
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
import glob
import json
import copy
import subprocess

import jsonschema
from empiar_depositor import empiar_depositor
from empiar.constants import (ASPERA_PASS, EMPIAR_TOKEN,
                              ASCP_PATH, DEPOSITION_SCHEMA,
                              DEPOSITION_TEMPLATE)
from tkMessageBox import showerror
from pyworkflow.em.protocol import EMProtocol
from pyworkflow.protocol import params
from pyworkflow.em.convert import ImageHandler
from pyworkflow.object import String
import pyworkflow.utils as pwutils


class EmpiarMappingError(Exception):
    """To raise it when we can't map Scipion data to EMPIAR data,
    e.g. we don't manage to assign an EMPIAR category to an image set."""
    pass


class EmpiarDepositor(EMProtocol):
    """
    Deposit image sets to empiar
    """
    _label = 'Empiar deposition'
    _ih = ImageHandler()
    _imageSetCategories = {
                              "SetOfMicrographs": "T1",
                              "SetOfMovies": 'T2',
                              # 'T3' : 'micrographs - focal pairs - unprocessed',
                              # 'T4' : 'micrographs - focal pairs - contrast inverted',
                              "SetOfMovieParticles": 'T5',  # : 'picked particles - single frame - unprocessed',
                              # 'T6' : 'picked particles - multiframe - unprocessed',
                              "SetOfParticles" : 'T7',  # 'picked particles - single frame - processed',
                              # "SetOfMovieParticles": 'T8',  # : 'picked particles - multiframe - processed',
                              "TiltPairSet": 'T9',   #   : 'tilt series',
                              "SetOfAverages": 'T10',  #  'class averages',
                              # 'OT' : 'other, in this case please specify the category in the second element.'
                            }
    _imageSetFormats = {
                           'mrc'    : 'T1',
                           'mrcs'   : 'T2',
                           'tiff'   : 'T3',
                           'img'    : 'T4',  # imagic
                           'dm3'    : 'T5',
                           'dm4'    : 'T6',
                           'spi'    : 'T7',  # spider
    }

    _experimentTypes = ['1', '2', '3', '4', '5', '6']
    _releaseDateTypes = ["IM", "EP", "HP", "H1"]
    _countryCodes = ['AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU',
                     'AW', 'AZ', 'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM',
                     'BN', 'BO', 'BR', 'BS', 'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF',
                     'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN', 'CO', 'CR', 'CU', 'CV', 'CW', 'CX',
                     'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE', 'EG', 'EH', 'ER',
                     'ES', 'ET', 'FI', 'FJ', 'FK', 'FM', 'FO', 'FR', 'FX', 'GA', 'GB', 'GD', 'GE',
                     'GF', 'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU',
                     'GW', 'GY', 'HK', 'HM', 'HN', 'HR', 'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN',
                     'IO', 'IQ', 'IR', 'IS', 'IT', 'JE', 'JM', 'JO', 'JP', 'KE', 'KG', 'KH', 'KI',
                     'KM', 'KN', 'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC', 'LI', 'LK', 'LR',
                     'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH', 'MK',
                     'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU', 'MV', 'MW', 'MX',
                     'MY', 'MZ', 'NA', 'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NU',
                     'NZ', 'OM', 'PA', 'PE', 'PF', 'PG', 'PH', 'PK', 'PL', 'PM', 'PN', 'PR', 'PS',
                     'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW', 'SA', 'SB', 'SC', 'SD',
                     'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS', 'ST',
                     'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK', 'TL', 'TM',
                     'TN', 'TO', 'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ',
                     'VA', 'VC', 'VE', 'VG', 'VI', 'VN', 'VU', 'WF', 'WS', 'XK', 'YE', 'YT', 'ZA',
                     'ZM', 'ZW']

    _voxelTypes = {
        _ih.DT_UCHAR: 'T1',   # 'UNSIGNED BYTE'
        _ih.DT_SCHAR: 'T2',   # 'SIGNED BYTE'
        _ih.DT_USHORT: 'T3',  # 'UNSIGNED 16 BIT INTEGER'
        _ih.DT_SHORT: 'T4',   # 'SIGNED 16 BIT INTEGER'
        _ih.DT_UINT: 'T5',    # 'UNSIGNED 32 BIT INTEGER'
        _ih.DT_INT: 'T6',     # 'SIGNED 32 BIT INTEGER'
        _ih.DT_FLOAT: 'T7'    # '32 BIT FLOAT'
    }

    OUTPUT_DEPO_JSON = 'deposition.json'
    OUTPUT_WORKFLOW = 'workflow.json'

    IMGSET_KEY = 'imagesets'
    IMGSET_NAME = "name"
    IMGSET_DIR = "directory"
    IMGSET_CAT = "category"
    IMGSET_HEADER_FORMAT = "header_format"
    IMGSET_DATA_FORMAT = "data_format"
    IMGSET_SIZE = "num_images_or_tilt_series"
    IMGSET_FRAMES = "frames_per_image"
    IMGSET_FRAME_MIN = "frame_range_min"
    IMGSET_FRAME_MAX = "frame_range_max"
    IMGSET_VOXEL_TYPE = "voxel_type"
    IMGSET_PIXEL_WIDTH = "pixel_width"
    IMGSET_PIXEL_HEIGHT = "pixel_height"
    IMGSET_DETAILS = "details"
    IMGSET_WIDTH = "image_width"
    IMGSET_HEIGHT = "image_height"

    _imageSetTemplate = {
        IMGSET_NAME: "",
        IMGSET_DIR: "/data/%s",
        IMGSET_CAT: "('%s', '%s')",
        IMGSET_HEADER_FORMAT: "('%s', '%s')",
        IMGSET_DATA_FORMAT: "('%s', '%s')",
        IMGSET_SIZE: 0,
        IMGSET_FRAMES: 0,
        IMGSET_FRAME_MIN: None,
        IMGSET_FRAME_MAX: None,
        IMGSET_VOXEL_TYPE: "('%s', '%s')",
        IMGSET_PIXEL_WIDTH: None,
        IMGSET_PIXEL_HEIGHT: None,
        IMGSET_DETAILS: "",
        IMGSET_WIDTH: 0,
        IMGSET_HEIGHT: 0
    }

    def __init__(self, **kwargs):
        EMProtocol.__init__(self, **kwargs)
        self.workflowDicts = []
        self.entryAuthorStr = ""
        self.workflowPath = String()
        self.depositionJsonPath = String()

    # --------------- DEFINE param functions ---------------

    def _defineParams(self, form):
        form.addSection(label='Entry')
        # form.addParam('workflowJson', params.PathParam,
        #               label='Workflow json', allowsNull=True,
        #               help='Path to the workflow json (obtained using the export option (right click on'
        #                     'one of your selected protocols). Will generate json of all protocols if not provided.')
        form.addParam("submit", params.BooleanParam,
                      label="Submit deposition", default=True,
                      help="Set to false to avoid submitting the deposition to empiar "
                           "(it will just be created locally).")
        form.addParam("resume", params.BooleanParam,
                      label="Resume upload", default=False, condition='submit',
                      help="Is this a continuation of a previous upload?")
        form.addParam('entryID', params.StringParam,
                      label="Entry ID", condition="resume", important=True,
                      help="EMPIAR entry ID - use if you wanna resume an upload")
        form.addParam('uniqueDir', params.StringParam, important=True,
                      label="Unique directory", condition="resume",
                      help="EMPIAR directory assigned to this deposition ID")
        form.addParam('depositionJson', params.PathParam, important=True,
                      label="Deposition json", condition="resume",
                      help="Path to the json file of the deposition we're about to resume.")

        form.addParam('jsonTemplate', params.PathParam, condition='not resume',
                      label="Custom json (Optional)", allowsNull=True,
                      help="Path to a customized template of the EMPIAR submission json, if you don't want to use the "
                           "default one.")
        form.addParam('entryTopLevel', params.StringParam, label="Top level folder",
                      validators=[params.NonEmpty], important=True,
                      help="How you want to name the top level folder of the empiar entry. \n This should be a "
                           "simple and descriptive name without special characters (:,?, spaces, etc). \n"
                           "If you're resuming an upload, this should be the same name you used to create the folder.")
        form.addParam('entryTitle', params.StringParam, label="Entry title", important=True, condition="not resume",
                      help="EMPIAR entry title. This should not be empty if not using a custom template.")
        form.addParam('entryAuthor', params.StringParam, label="Entry author", important=True, condition="not resume",
                      help='EMPIAR entry author in the form "LastName, Initials" e.g. Smith, JW\n'
                           'This should not be empty if not using a custom template.')
        form.addParam('experimentType', params.EnumParam, label="Experiment type", condition="not resume",
                      choices=self._experimentTypes, default=2, important=True,
                      help="EMPIAR experiment type:\n"
                           "1 - image data collected using soft x-ray tomography\n"
                           "2 - simulated data, for instance, created using InSilicoTEM\n"
                           "   (note: simulated data accepted in special circumstances such\n"
                           "    as test/training sets for validation challenges: you need to\n"
                           "    ask for and be granted permission PRIOR to deposition otherwise\n"
                           "    the dataset will be rejected by EMPIAR)\n"
                           "3 - raw image data relating to structures deposited to the Electron Microscopy Data Bank\n"
                           "4 - image data collected using serial block-face scanning electron microscopy \n"
                           "    (like the Gatan 3View system)\n"
                           "5 - image data collected using focused ion beam scanning electron microscopy\n"
                           "6 - integrative hybrid modelling data.")
        form.addParam('releaseDate', params.EnumParam, label="Release date", condition="not resume",
                      choices=self._releaseDateTypes, default=2, important=True,
                      help="EMPIAR release date:\n"
                           "Options for releasing entry to the public: \n"
                           "IM - directly after the submission has been processed\n"
                           "EP - after the related EMDB entry has been released\n"
                           "HP - after the related primary citation has been published\n"
                           "H1 - delay release of entry by one year from the date of deposition"
                      )

        form.addSection(label='Image sets')
        self.inputSetsParam = form.addParam('inputSets', params.MultiPointerParam,
                                            label="Input set", important=True, condition="not resume",
                                            pointerClass=','.join(self._imageSetCategories.keys()), minNumObjects=1,
                                            help='Select one set (of micrographs, particles,'
                                                 ' volumes, etc.) to be deposited to EMPIAR.')
        # form.addParam('micSet', params.PointerParam, pointerClass='SetOfMicrographs,SetOfMovies,SetOfParticles',
        #               label='Image set', important=False,
        #               help='Image set to be uploaded to EMPIAR\n')

        form.addSection(label="Principal investigator")
        form.addParam('piFirstName', params.StringParam, label='First name', condition="not resume",
                      help="PI first name e.g. Juan- this should not be empty if not using a custom template.")
        form.addParam('piLastName', params.StringParam, label='Last name', condition="not resume",
                      help='PI Last name e.g. Perez - this should not be empty if not using a custom template.')
        form.addParam('piOrg', params.StringParam, label='organization', condition="not resume",
                      help="The name of the organization e.g. Biocomputing Unit, CNB-CSIC \n"
                           "This should not be empty if not using a custom template.")
        form.addParam('piEmail', params.StringParam, label="Email", condition="not resume",
                      help='PI Email address e.g. jperez@org.es - '
                           'this should not be empty if not using a custom template.')
        form.addParam('piCountry', params.StringParam, label="Country", condition="not resume",
                      help="Two letter country code eg. ES. This should not be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(self._countryCodes))


        form.addSection(label="Corresponding Author")
        form.addParam('caFirstName', params.StringParam, label='First name', condition="not resume",
                      help="Corresponding author's first name e.g. Juan. "
                           "This should not be empty if not using a custom template. ")
        form.addParam('caLastName', params.StringParam, label='Last name', condition="not resume",
                      help="Corresponding author's Last name e.g. Perez. "
                           "This should not be empty if not using a custom template.")
        form.addParam('caOrg', params.StringParam, label='organization', condition="not resume",
                      help="The name of the organization e.g. Biocomputing Unit, CNB-CSIC."
                           "This should not be empty if not using a custom template.")
        form.addParam('caEmail', params.StringParam, label="Email", condition="not resume",
                      help="Corresponding author's Email address e.g. jperez@org.es. "
                           "This should not be empty if not using a custom template.")
        form.addParam('caCountry', params.StringParam, label="Country", condition="not resume",
                      help="Two letter country code e.g. ES. This should not be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(self._countryCodes))



    # --------------- INSERT steps functions ----------------

    def _insertAllSteps(self):
        self._insertFunctionStep('createDepositionStep')
        if self.submit:
            self._insertFunctionStep('submitDepositionStep')

    # --------------- STEPS functions -----------------------

    def createDepositionStep(self):
        # make folder in extra
        if not self.resume:
            pwutils.makePath(self._getExtraPath(self.entryTopLevel.get()))

            # export workflow json
            self.exportWorkflow()

            # create deposition json
            jsonTemplatePath = self.jsonTemplate.get('').strip() or DEPOSITION_TEMPLATE

            entryAuthorStr = self.entryAuthor.get().split(',')
            self.entryAuthorStr = "'%s', '%s'" % (entryAuthorStr[0].strip(), entryAuthorStr[1].strip())
            self.releaseDate = self._releaseDateTypes[self.releaseDate.get()]
            self.experimentType = self.experimentType.get()+1
            jsonStr = open(jsonTemplatePath, 'rb').read().decode('utf-8')
            jsonStr = jsonStr % self.__dict__
            depoDict = json.loads(jsonStr)
            imageSets = self.processImageSets()
            depoDict[self.IMGSET_KEY] = imageSets
            depoJson = self.getTopLevelPath(self.OUTPUT_DEPO_JSON)
            with open(depoJson, 'w') as f:
                # f.write(jsonStr.encode('utf-8'))
                json.dump(depoDict, f, indent=4)
            # self.depositionJsonPath = depoJson
            self.depositionJsonPath.set(depoJson)
        else:
            self.depositionJsonPath.set(self.depositionJson.get())
            with open(self.depositionJson.get()) as f:
                depoDict = json.load(f)
        self._store()
        self.validateDepoJson(depoDict)

    def submitDepositionStep(self):
        depositorCall = '%(resume)s %(token)s %(depoJson)s %(ascp)s %(dataDir)s'
        args = {'resume': '-r %s %s' % (self.entryID, self.uniqueDir) if self.resume else "",
                'token': os.environ[EMPIAR_TOKEN],
                'depoJson': os.path.abspath(self.depositionJsonPath.get()),
                'ascp': os.environ[ASCP_PATH],
                'dataDir': os.path.abspath(self.getTopLevelPath())
                }

        depositorCall = depositorCall % args
        print("Empiar depositor call: %s" % depositorCall)
        empiar_depositor.main(depositorCall.split())

    # --------------- INFO functions -------------------------

    def _validate(self):
        errors = []
        if self.submit:
            if EMPIAR_TOKEN not in os.environ:
                errors.append("Environment variable %s not set. Please set your %s in ~/.config/scipion/scipion.conf "
                              "or in your environment." % (EMPIAR_TOKEN, EMPIAR_TOKEN))
            if ASPERA_PASS not in os.environ:
                errors.append("Environment variable %s not set. Please set your %s in ~/.config/scipion/scipion.conf "
                              "or in your environment." % (ASPERA_PASS, ASPERA_PASS))
        return errors

    def _citations(self):
        return ['Iudin2016']

    def _summary(self):
        summary = []
        if self.depositionJsonPath.get():
            summary.append('Generated deposition files:')
            summary.append('- [[%s][Scipion workflow]]' % self.workflowPath)
            summary.append('- [[%s][Deposition json]]' % self.depositionJsonPath)
        else:
            summary.append('No deposition files generated yet')

        return summary

    def _methods(self):
        return []

    # -------------------- UTILS functions -------------------------

    def getTopLevelPath(self, *paths):
        return os.path.join(self._getExtraPath(self.entryTopLevel.get()), *paths)

    def exportWorkflow(self):
        project = self.getProject()
        workflowProts = [p for p in project.getRuns()]  # workflow prots are all prots if no json provided
        workflowJsonPath = os.path.join(project.path, self.getTopLevelPath(self.OUTPUT_WORKFLOW))
        protDicts = project.getProtocolsDict(workflowProts)

        for inputSetPointer in self.inputSets:
            inputSet = inputSetPointer.get()
            setName = inputSet.getObjName()
            setParentId = inputSet.getObjParentId()
            setParentObj = project.getObject(setParentId)
            protDicts[setParentId]['filesPath'] = os.path.join('.', setName)
            pwutils.createLink(setParentObj._getExtraPath(), self.getTopLevelPath(setName))

        with open(workflowJsonPath, 'w') as f:
            f.write(json.dumps(list(protDicts.values()), indent=4, separators=(',', ': ')))

        self.workflowPath.set(workflowJsonPath)

        return workflowJsonPath

    def validateDepoJson(self, depoDict):
        with open(DEPOSITION_SCHEMA) as f:
            schema = json.load(f)
        valid = jsonschema.validate(depoDict, schema)  # raises exception if not valid
        return True


    # --------------- imageSet utils -------------------------

    def getEmpiarCategory(self, imageSet):
        className = imageSet.getClassName()
        category = self._imageSetCategories.get(className, None)
        if category is None:
            raise EmpiarMappingError('Could not assign an EMPIAR category to image set %s' % imageSet.getObjName())
        else:
            return category, ''

    def getEmpiarFormat(self, imagePath):
        ext = pwutils.getExt(imagePath).lower().strip('.')
        imgFormat = self._imageSetFormats.get(ext, None)
        if imgFormat is None:
            raise EmpiarMappingError('Image format not recognized: ' % ext)
        else:
            return imgFormat, ''

    def getVoxelType(self, imageObj):
        dataType = self._ih.getDataType(imageObj)
        empiarType = self._voxelTypes.get(dataType, None)
        if empiarType == None:
            raise EmpiarMappingError('Could not map voxel type for image %s' % imageObj.getFilename())
        else:
            return empiarType, ''

    def getImageSetDict(self, imageSet):
        firstImg = imageSet.getFirstItem()
        firstFileName = firstImg.getFileName()
        dims = imageSet.getDimensions()
        micSetDict = copy.deepcopy(self._imageSetTemplate)
        micSetDict[self.IMGSET_NAME] = imageSet.getObjName()
        micSetDict[self.IMGSET_DIR] = "/data/%s" % imageSet.getObjName()
        micSetDict[self.IMGSET_CAT] = "('%s', '%s')" % self.getEmpiarCategory(imageSet)
        micSetDict[self.IMGSET_HEADER_FORMAT] = "('%s', '%s')" % self.getEmpiarFormat(firstFileName)
        micSetDict[self.IMGSET_DATA_FORMAT] = "('%s', '%s')" % self.getEmpiarFormat(firstFileName)
        micSetDict[self.IMGSET_SIZE] = len(imageSet)
        micSetDict[self.IMGSET_FRAMES] = dims[2]
        micSetDict[self.IMGSET_VOXEL_TYPE] = "('%s', '%s')" % self.getVoxelType(firstImg)
        micSetDict[self.IMGSET_PIXEL_WIDTH] = imageSet.getSamplingRate()
        micSetDict[self.IMGSET_PIXEL_HEIGHT] = imageSet.getSamplingRate()
        micSetDict[self.IMGSET_DETAILS] = "/data/%s" % os.path.basename(self.workflowPath.get())
        micSetDict[self.IMGSET_WIDTH] = dims[0]
        micSetDict[self.IMGSET_HEIGHT] = dims[1]
        return micSetDict

    def processImageSets(self):
        inputSets = [s.get() for s in self.inputSets]
        imgSetDicts = []
        for imgSet in inputSets:
            imgSetDict = self.getImageSetDict(imgSet)
            imgSetDicts.append(imgSetDict)
        return imgSetDicts
