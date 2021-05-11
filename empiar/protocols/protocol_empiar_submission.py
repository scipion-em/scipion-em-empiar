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
import json
import copy
import requests
import re
from pkg_resources import resource_filename

import jsonschema
from empiar_depositor import empiar_depositor
from empiar.constants import (ASPERA_PASS, EMPIAR_TOKEN, EMPIAR_DEVEL_MODE,
                              ASCP_PATH)
from pwem import emlib, Domain
from pwem.protocols import EMProtocol
from pwem.objects import Class2D, Class3D, Image, CTFModel, Volume, Micrograph, Movie, Particle, SetOfCoordinates
from pyworkflow.protocol import params
from pyworkflow.object import String, Set
import pyworkflow.utils as pwutils
from .. import Plugin
from pyworkflow.project import config
from PIL import Image as ImagePIL
from PIL import ImageDraw

DEPOSITION_TEMPLATE = resource_filename('empiar', '/'.join(('templates', 'empiar_deposition_template.json')))
DEPOSITION_SCHEMA = resource_filename('empiar_depositor', '/empiar_deposition.schema.json')

class EmpiarMappingError(Exception):
    """To raise it when we can't map Scipion data to EMPIAR data,
    e.g. we don't manage to assign an EMPIAR category to an image set."""
    pass


class EmpiarDepositor(EMProtocol):
    """
    Deposits image sets to EMPIAR.
    """
    _label = 'Empiar deposition'
    _ih = emlib.image.ImageHandler()
    _imageSetCategories = {
                              "SetOfMicrographs": "T1",
                              "SetOfMovies": 'T2',
                              # 'T3' : 'micrographs - focal pairs - unprocessed',
                              # 'T4' : 'micrographs - focal pairs - contrast inverted',
                              "SetOfMovieParticles": 'T5',  # : 'picked particles - single frame - unprocessed',
                              # 'T6' : 'picked particles - multiframe - unprocessed',
                              "SetOfParticles": 'T7',  # 'picked particles - single frame - processed',
                              # "SetOfMovieParticles": 'T8',  # : 'picked particles - multiframe - processed',
                              "TiltPairSet": 'T9',  # : 'tilt series',
                              "SetOfAverages": 'T10',  # 'class averages',
                              # 'OT' : 'other, in this case please specify the category in the second element.'
                            }
    _imageSetFormats = {
                           'mrc': 'T1',
                           'mrcs': 'T2',
                           'tiff': 'T3',
                           'img': 'T4',  # imagic
                           'dm3': 'T5',
                           'dm4': 'T6',
                           'spi': 'T7',  # spider
    }

    _experimentTypes = ['1', '2', '3', '4', '5', '6']
    _releaseDateTypes = ["RE", "EP", "HP", "HO"]
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
        emlib.DT_UCHAR: 'T1',   # 'UNSIGNED BYTE'
        emlib.DT_SCHAR: 'T2',   # 'SIGNED BYTE'
        emlib.DT_USHORT: 'T3',  # 'UNSIGNED 16 BIT INTEGER'
        emlib.DT_SHORT: 'T4',   # 'SIGNED 16 BIT INTEGER'
        emlib.DT_UINT: 'T5',    # 'UNSIGNED 32 BIT INTEGER'
        emlib.DT_INT: 'T6',     # 'SIGNED 32 BIT INTEGER'
        emlib.DT_FLOAT: 'T7'    # '32 BIT FLOAT'
    }

    _grantOwnershipBasedOn = ['username', 'email', 'ORCiD']

    OUTPUT_DEPO_JSON = 'deposition.json'
    OUTPUT_WORKFLOW = 'workflow.json'

    ENTRY_DIR = 'data'

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

    OUTPUT_NAME = 'outputName'
    OUTPUT_TYPE = 'outputType'
    OUTPUT_ITEMS = 'outputItems'
    OUTPUT_SIZE = 'outputSize'
    ITEM_ID = 'item_id'
    ITEM_REPRESENTATION = 'item_representation'
    DIR_IMAGES = 'images_representation'

    _outputTemplate = {
        OUTPUT_NAME: ""
    }

    SCIPION_WORKFLOW_KEY = 'scipion'
    SCIPION_WORKFLOW = 'scipion_workflow'

    _workflowTemplate = {
        SCIPION_WORKFLOW: ""
    }

    def __init__(self, **kwargs):
        EMProtocol.__init__(self, **kwargs)
        self.workflowDicts = []
        self.entryAuthorStr = ""
        self.workflowPath = String()
        self.depositionJsonPath = String()
        self.entryID = String()
        self.uniqueDir = String()

    # --------------- DEFINE param functions ---------------

    def _defineParams(self, form):
        form.addSection(label='Entry')
        form.addParam("deposit", params.BooleanParam,
                      label="Make deposition", default=True,
                      help="Set to false to avoid performing a deposition to EMPIAR "
                           "(it will just be created locally).")
        #form.addParam("cwl", params.BooleanParam,
        #              label="Create CWL", default=True,
        #              help="Set to yes if you want to generate a CWL file.")
        form.addParam("resume", params.BooleanParam,
                      label="Update existing entry", default=False, condition='deposit',
                      help="Is this a continuation of a previous deposition?")
        form.addParam("submit", params.BooleanParam,
                      label="Submit", default=False, condition='deposit',
                      help="Is this the last entry update? If so, the EMPIAR entry will be submitted and no future changes can be done (except for providing the EMDB codes related with the EMPIAR entry).")
        form.addParam('jsonTemplate', params.PathParam,
                      label="Custom json (Optional)", allowsNull=True,
                      help="Path to a customized template of the EMPIAR submission json, if you don't want to use the "
                           "default one.")
        form.addParam('entryTopLevel', params.StringParam, label="Top level folder",
                      validators=[params.NonEmpty], important=True,
                      help="How you want to name the top level folder of the EMPIAR entry. \n This should be a "
                           "simple and descriptive name without special characters (:,?, spaces, etc). ")
        form.addParam('entryTitle', params.StringParam, label="Entry title", important=True,
                      help="EMPIAR entry title. This should not be empty if not using a custom template.")
        form.addParam('entryAuthor', params.StringParam, label="Entry author", important=True,
                      help='EMPIAR entry author in the form "LastName, Initials" e.g. Smith, JW\n'
                           'This should not be empty if not using a custom template.')
        form.addParam('experimentType', params.EnumParam, label="Experiment type",
                      choices=self._experimentTypes, default=2, important=True,
                      help="EMPIAR experiment type:\n"
                           "1 - image data collected using soft x-ray tomography\n"
                           "2 - simulated data, for instance, created using InSilicoTEM \n"
                           "(note: we only accept simulated data in special circumstances such as test/training sets \n"
                           "for validation challenges: you need to ask for and be granted permission PRIOR to deposition \n"
                           "otherwise the dataset will be rejected)\n"
                           "3 - raw image data relating to structures deposited to the Electron Microscopy Data Bank\n"
                           "4 - image data collected using serial block-face scanning electron microscopy \n"
                           "    (like the Gatan 3View system)\n"
                           "5 - image data collected using focused ion beam scanning electron microscopy\n"
                           "6 - integrative hybrid modelling data\n"
                           "7 - correlative light-electron microscopy\n"
                           "8 - correlative light X-ray microscopy\n"
                           "9 - microcrystal electron diffraction")
        form.addParam('releaseDate', params.EnumParam, label="Release date",
                      choices=self._releaseDateTypes, default=0, important=True,
                      help="EMPIAR release date:\n"
                           "Options for releasing entry to the public: \n"
                           "RE - directly after the submission has been processed\n"
                           "EP - after the related EMDB entry has been released\n"
                           "HP - after the related primary citation has been published\n"
                           "HO - delay release of entry by one year from the date of deposition"
                      )

        form.addParam('citations', params.FileParam, label='Citations bibtex', help="File containing a bibtex with citations.")

        form.addSection(label='Image sets')
        self.inputSetsParam = form.addParam('inputSets', params.MultiPointerParam,
                                            label="Input set", important=True,
                                            pointerClass=','.join(self._imageSetCategories.keys()), minNumObjects=1,
                                            help='Select one set (of micrographs, particles,'
                                                 ' volumes, etc.) to be deposited to EMPIAR.')
        # form.addParam('micSet', params.PointerParam, pointerClass='SetOfMicrographs,SetOfMovies,SetOfParticles',
        #               label='Image set', important=False,
        #               help='Image set to be uploaded to EMPIAR\n')

        form.addSection(label="Principal investigator")
        form.addParam('piFirstName', params.StringParam, label='First name',
                      help="PI first name e.g. Juan. "
                           "This should not be empty if not using a custom template.")
        form.addParam('piLastName', params.StringParam, label='Last name',
                      help="PI Last name e.g. Perez. "
                           "This should not be empty if not using a custom template.")
        form.addParam('piOrg', params.StringParam, label='Organization',
                      help="The name of the organization e.g. Biocomputing Unit, CNB-CSIC. "
                           "This should not be empty if not using a custom template.")
        form.addParam('piEmail', params.StringParam, label="Email",
                      help="PI Email address e.g. jperez@org.es. "
                           "This should not be empty if not using a custom template.")
        form.addParam('piPost', params.StringParam, label="Post or zip",
                      help="Post or ZIP code. This should not be empty if not using a custom template.")
        form.addParam('piTown', params.StringParam, label="Town or city",
                      help="Town or city name. This should not be empty if not using a custom template.")
        form.addParam('piCountry', params.StringParam, label="Country",
                      help="Two letter country code eg. ES. This should not be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(self._countryCodes))

        form.addSection(label="Corresponding Author")
        form.addParam('caFirstName', params.StringParam, label='First name',
                      help="Corresponding author's first name e.g. Juan. "
                           "This should not be empty if not using a custom template. ")
        form.addParam('caLastName', params.StringParam, label='Last name',
                      help="Corresponding author's Last name e.g. Perez. "
                           "This should not be empty if not using a custom template.")
        form.addParam('caOrg', params.StringParam, label='Organization',
                      help="The name of the organization e.g. Biocomputing Unit, CNB-CSIC. "
                           "This should not be empty if not using a custom template.")
        form.addParam('caEmail', params.StringParam, label="Email",
                      help="Corresponding author's Email address e.g. jperez@org.es. "
                           "This should not be empty if not using a custom template.")
        form.addParam('caPost', params.StringParam, label="Post or zip",
                      help="Post or ZIP code. This should not be empty if not using a custom template.")
        form.addParam('caTown', params.StringParam, label="Town or city",
                      help="Town or city name. This should not be empty if not using a custom template.")
        form.addParam('caCountry', params.StringParam, label="Country",
                      help="Two letter country code e.g. ES. This should not be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(self._countryCodes))

        form.addSection(label="Transfer entry ownership")
        form.addParam("ownershipBasedOn", params.EnumParam, label="Based on",
                      choices=self._grantOwnershipBasedOn, default=0, important=True,
                      help="You may want to transfer EMPIAR entry ownership to other user. Here you specify if you are providing the user username, email or ORCiD.")
        form.addParam("newOwnerId", params.StringParam, label="User ID", important=True,
                      help="The user username, email or ORCiD.")

        form.addSection(label="EMDB codes (post-submission request)")
        form.addParam('EMDBrefs', params.StringParam, label="EMDB codes", help="If you want to request to EMPIAR annotators to update the EMPIAR entry (already submitted) with the EMDB accesion codes, you can provide them here separated by comma.")

    # --------------- INSERT steps functions ----------------

    def _insertAllSteps(self):
        if self.EMDBrefs != '':
            self._insertFunctionStep('provideEMDBcodesStep')
        else:
            self._insertFunctionStep('createDepositionStep')
            if self.deposit:
                self._insertFunctionStep('makeDepositionStep')
            #if self.cwl:
            #    self._insertFunctionStep('createCWLStep')

    # --------------- STEPS functions -----------------------

    def createDepositionStep(self):
        # make folder in extra
        pwutils.makePath(self._getExtraPath(self.entryTopLevel.get()))
        pwutils.makePath(self.getTopLevelPath(self.DIR_IMAGES))

        # export workflow json
        self.exportWorkflow()

        # If deposition is not happening
        if not self.deposit:
            return
        # create deposition json
        jsonTemplatePath = self.jsonTemplate.get('').strip() or DEPOSITION_TEMPLATE

        entryAuthorStr = self.entryAuthor.get().split(',')
        self.entryAuthorStr = "'%s', '%s'" % (entryAuthorStr[0].strip(), entryAuthorStr[1].strip())
        self.releaseDate = self.getEnumText('releaseDate')
        self.experimentType = self.experimentType.get()+1

        jsonStr = open(jsonTemplatePath, 'rb').read().decode('utf-8')
        jsonStr = jsonStr % self.__dict__
        depoDict = json.loads(jsonStr)
        imageSets = self.processImageSets()
        if len(imageSets) > 0:
            print("Imagesets is not empty")
            depoDict[self.IMGSET_KEY] = imageSets

        if self.citations.get() is not None:
            file = open(self.citations.get(), "r")
            citationJson = json.load(file)
            #cita = pwutils.parseBibTex(str)
            #authors = cita['author'].split()
            #for author in authors:
            #    depoDict['authors'].append({'name':author.strip()})
            #for attr in cita.keys():
            #    depoDict[attr] = cita[attr]
            citationJson['editors'] = []
            depoDict['citation'][0] = citationJson
            file.close()


        depoDict[self.SCIPION_WORKFLOW_KEY] = self.getScipionWorkflow()
        depoJson = self.getTopLevelPath(self.OUTPUT_DEPO_JSON)
        with open(depoJson, 'w') as f:
            # f.write(jsonStr.encode('utf-8'))
            json.dump(depoDict, f, indent=4)
        # self.depositionJsonPath = depoJson
        self.depositionJsonPath.set(depoJson)

        self._store()
        self.validateDepoJson(depoDict)

    def makeDepositionStep(self):
        depositorCall = '%(resume)s %(token)s %(depoJson)s %(ascp)s %(devel)s %(data)s -o %(submit)s %(grant)s'
        grantCall = "%(basedOn)s %(userID)s:1"
        grantArgs = {'basedOn': '-ge' if self.getEnumText('ownershipBasedOn') == 'email' else '-gu',
                     'userID': self.newOwnerId}
        args = {'resume': '-r %s %s' % (self.entryID, self.uniqueDir) if self.resume else "",
                'token': os.environ[EMPIAR_TOKEN],
                'depoJson': os.path.abspath(self.depositionJsonPath.get()),
                'ascp': '-a %s' % os.environ[ASCP_PATH],
                'devel': '-d' if (EMPIAR_DEVEL_MODE in os.environ and os.environ[EMPIAR_DEVEL_MODE] == '1') else '',
                'data': os.path.abspath(self.getTopLevelPath()),
                'submit': '' if self.submit else '-s',
                'grant': grantCall % grantArgs if self.newOwnerId != '' else ''
                }

        depositorCall = depositorCall % args
        print("Empiar depositor call: %s" % depositorCall)
        dep_result = empiar_depositor.main(depositorCall.split())
        self.entryID.set(dep_result[0])
        self.uniqueDir.set(dep_result[1])
        self._store()

    def createCWLStep(self):
        # This function will create a CWL file with workflow description
        pass

    def provideEMDBcodesStep(self):
        # This function requests to EMPIAR annotators a post-submission change for provide the EMDB entry/ies code/s related with the EMPIAR entry
        requests.packages.urllib3.disable_warnings()
        url = 'https://wwwdev.ebi.ac.uk/pdbe/emdb/external_test/master/empiar/deposition/api/v1/request_changes/' if (EMPIAR_DEVEL_MODE in os.environ and os.environ[EMPIAR_DEVEL_MODE] == '1') else 'https://www.ebi.ac.uk/pdbe/emdb/empiar/deposition/api/v1/request_changes/'
        data = {'entry_id': str(self.entryID), 'msg': 'I would like to update this entry with the EMDB code/s: ' + self.EMDBrefs.get()}
        headers = {'Content-Type': 'application/json', 'Authorization': 'Token ' + os.environ[EMPIAR_TOKEN]}
        response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        if response.status_code == 200:
            print('The request to EMPIAR annotators for adding the EMDB entry/ies code/s was sent successfully')
        else:
            print('The request to EMPIAR annotators for adding the EMDB entry/ies code/s was not successful')


    # --------------- INFO functions -------------------------

    def _validate(self):
        errors = []
        if self.deposit:
            if EMPIAR_TOKEN not in os.environ:
                errors.append("Environment variable %s not set." % EMPIAR_TOKEN)

            if ASPERA_PASS not in os.environ:
                errors.append("Environment variable %s not set." % ASPERA_PASS)

            if not os.path.exists(Plugin.getVar(ASCP_PATH)):
                errors.append("Variable %s points to %s (aspera client) but it does not exists." % (ASCP_PATH, Plugin.getVar(ASCP_PATH)))

            if errors:
                errors.append("Please review the setup section at %s ." % Plugin.getUrl())

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

        # labels and colors
        settingsPath = os.path.join(project.path, project.settingsPath)
        settings = config.ProjectSettings.load(settingsPath)
        labels = settings.getLabels()
        labelsDict = {}
        for label in labels:
            labelInfo = label._values
            labelsDict[labelInfo['name']] = labelInfo['color']

        protsConfig = settings.getNodes()
        protsLabelsDict = {}
        for protConfig in protsConfig:
            protConfigInfo = protConfig._values
            if len(protConfigInfo['labels']) > 0:
                protsLabelsDict[protConfigInfo['id']] = []
                for label in protConfigInfo['labels']:
                    protsLabelsDict[protConfigInfo['id']].append(label)

        # Add extra info to protocosDict
        for prot in workflowProts:
            # Get summary and add input and output information
            summary = prot.summary()
            for a, input in prot.iterInputAttributes():
                summary.append("Input: %s \n" % str(input.get()))

            protDicts[prot.getObjId()]['output'] = []
            num = 0
            for a, output in prot.iterOutputAttributes():
                print('output key is %s' % a)
                num += 1
                protDicts[prot.getObjId()]['output'].append(self.getOutputDict(output))
                if num == 1:
                    summary.append("Output: %s" % str(output))
                else:
                    summary.append(str(output))

            protDicts[prot.getObjId()]['summary'] = ''.join(summary)

            # Get log (stdout)
            outputs = []
            logs = list(prot.getLogPaths())
            if pwutils.exists(logs[0]):
                logPath = self.getTopLevelPath(self.DIR_IMAGES, "%s_%s.log" % (prot.getObjId(), prot.getClassName()))
                pwutils.copyFile(logs[0], logPath)
                outputs = logPath

            protDicts[prot.getObjId()]['log'] =  outputs

            # labels
            if prot.getObjId() in protsLabelsDict.keys():
                protDicts[prot.getObjId()]['label'] = protsLabelsDict[prot.getObjId()]
                protDicts[prot.getObjId()]['labelColor'] = []
                for label in protDicts[prot.getObjId()]['label']:
                    protDicts[prot.getObjId()]['labelColor'].append(labelsDict[label])

            # Get plugin and binary version
            protDicts[prot.getObjId()]['plugin'] = prot.getClassPackageName()
            if len(outputs) > 0:
                with open(logPath) as log:
                    for line in log:
                        if re.search(r'plugin v', line):
                            version = line.split(':')[1].replace(' ', '').replace('\n', '')
                            protDicts[prot.getObjId()]['pluginVersion'] = version

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
            raise EmpiarMappingError('Image format not recognized: %s' % ext)
        else:
            return imgFormat, ''

    def getVoxelType(self, imageObj):
        dataType = self._ih.getDataType(imageObj)
        empiarType = self._voxelTypes.get(dataType, None)
        if empiarType is None:
            raise EmpiarMappingError('Could not map voxel type for image %s' % imageObj.getFilename())
        else:
            return empiarType, ''

    def getImageSetDict(self, imageSet):
        firstImg = imageSet.getFirstItem()
        firstFileName = firstImg.getFileName()
        dims = imageSet.getDimensions()
        micSetDict = copy.deepcopy(self._imageSetTemplate)
        micSetDict[self.IMGSET_NAME] = imageSet.getObjName()
        micSetDict[self.IMGSET_DIR] = "%s/%s/%s" % (self.ENTRY_DIR, self.entryTopLevel.get(), imageSet.getObjName())
        micSetDict[self.IMGSET_CAT] = "('%s', '%s')" % self.getEmpiarCategory(imageSet)
        micSetDict[self.IMGSET_HEADER_FORMAT] = "('%s', '%s')" % self.getEmpiarFormat(firstFileName)
        micSetDict[self.IMGSET_DATA_FORMAT] = "('%s', '%s')" % self.getEmpiarFormat(firstFileName)
        micSetDict[self.IMGSET_SIZE] = len(imageSet)
        micSetDict[self.IMGSET_FRAMES] = dims[2]
        micSetDict[self.IMGSET_VOXEL_TYPE] = "('%s', '%s')" % self.getVoxelType(firstImg)
        micSetDict[self.IMGSET_PIXEL_WIDTH] = imageSet.getSamplingRate()
        micSetDict[self.IMGSET_PIXEL_HEIGHT] = imageSet.getSamplingRate()
        micSetDict[self.IMGSET_DETAILS] = "%s/%s/%s" % (self.ENTRY_DIR, self.entryTopLevel.get(), os.path.basename(self.workflowPath.get()))
        micSetDict[self.IMGSET_WIDTH] = dims[0]
        micSetDict[self.IMGSET_HEIGHT] = dims[1]
        return micSetDict

    def processImageSets(self):
        inputSets = [s.get() for s in self.inputSets]
        imgSetDicts = []
        for imgSet in inputSets:
            try:
                imgSetDict = self.getImageSetDict(imgSet)
            except:
                pass
            else:
                imgSetDicts.append(imgSetDict)
        return imgSetDicts

    def getScipionWorkflow(self):
        workflowDict = copy.deepcopy(self._workflowTemplate)
        workflowDict[self.SCIPION_WORKFLOW] = "%s/%s/%s" % (self.ENTRY_DIR, self.entryTopLevel.get(), os.path.basename(self.workflowPath.get()))
        return workflowDict

    def getOutputDict(self, output):
        self.outputName = output.getObjName()
        outputDict = {}
        outputDict[self.OUTPUT_NAME] = output.getObjName()
        outputDict[self.OUTPUT_TYPE] = output.getClassName()

        items = []

        # If output is a Set get a list with all items
        if isinstance(output, Set):
            outputDict[self.OUTPUT_SIZE] = output.getSize()
            count = 0
            if isinstance(output, SetOfCoordinates):
                coordinatesDict = {}
                for micrograph in output.getMicrographs(): # get the first three micrographs
                    count += 1
                    # apply a low pass filter
                    args = " -i %s -o %s --fourier low_pass %f" % (micrograph.getLocation()[1], self._getTmpPath(os.path.basename(micrograph.getFileName())), 0.05)
                    getEnviron = Domain.importFromPlugin('xmipp3', 'Plugin', doRaise=True).getEnviron
                    self.runJob('xmipp_transform_filter', args, env=getEnviron())
                    # save jpg
                    repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.replaceBaseExt(micrograph.getFileName(), 'jpg')))
                    self._ih.convert(self._getTmpPath(os.path.basename(micrograph.getFileName())), os.path.join(self.getProject().path, repPath))
                    coordinatesDict[micrograph.getMicName()] = {'path': repPath, 'Xdim': micrograph.getXDim(), 'Ydim': micrograph.getYDim()}

                    items.append({self.ITEM_REPRESENTATION: repPath})
                    if count == 3: break;

                for coordinate in output: # for each micrograph, get its coordinates
                    if coordinate.getMicName() in coordinatesDict:
                        coordinatesDict[coordinate.getMicName()].setdefault('coords', []).append([coordinate.getX(), coordinate.getY()])

                for micrograph, values in coordinatesDict.items(): # draw coordinates in micrographs jpgs
                    if 'coords' in values:
                        image = ImagePIL.open(values['path']).convert('RGB')
                        W_mic = values['Xdim']
                        H_mic = values['Ydim']
                        W_jpg, H_jpg = image.size
                        draw = ImageDraw.Draw(image)
                        r = W_jpg / 256
                        for coord in values['coords']:
                            x = coord[0] * (W_jpg / W_mic)
                            y = coord[1] * (H_jpg / H_mic)
                            draw.ellipse((x - r, y - r, x + r, y + r), fill=(0, 255, 0))
                        image.save(values['path'], quality=95)

            else:
                for item in output.iterItems():
                    itemDict = self.getItemDict(item)
                    items.append(itemDict)
                    count += 1
                    # In some types get only a limited number of items
                    if (isinstance(item, Micrograph) or isinstance(item, Movie) or isinstance(item, CTFModel)) and count == 3: break;
                    if isinstance(item, Particle) and count == 15: break;

        # If it is a single object then only one item is present
        else:
            items.append(self.getItemDict(output))

        outputDict[self.OUTPUT_ITEMS] = items

        return outputDict

    def getItemDict(self, item):
        itemDict = {}
        attributes = item.getAttributes()
        for key, value in attributes:
            # Skip attributes that are Pointer
            if not value.isPointer():
                itemDict[key] = str(value)

        itemDict[self.ITEM_ID] = item.getObjId()

        try:
            # Get item representation
            if isinstance(item, Class2D):
                # use representative as item representation
                repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s_%s' % (self.outputName, item.getRepresentative().getIndex(), pwutils.replaceBaseExt(item.getRepresentative().getFileName(), 'jpg')))
                itemPath = item.getRepresentative().getLocation()
                self._ih.convert(itemPath, os.path.join(self.getProject().path, repPath))

                if '_size' in itemDict:  # write number of particles over the class
                    text = itemDict['_size'] + " ptcls"
                    image = ImagePIL.open(repPath).convert('RGB')
                    W, H = image.size
                    draw = ImageDraw.Draw(image)
                    draw.text((5, H - 15), text, fill=(0, 255, 0))
                    image.save(repPath, quality=95)

                itemDict[self.ITEM_REPRESENTATION] = repPath

            elif isinstance(item, Class3D):
                # Get all slices in x,y and z directions of representative to represent the class
                repDir = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.removeBaseExt(item.getRepresentative().getFileName())))
                pwutils.makePath(repDir)
                if item.getFileName().endswith('.mrc'):
                    item.setFileName(item.getFileName() + ':mrc')
                I = emlib.Image(item.getRepresentative().getFileName())
                I.writeSlices(os.path.join(repDir,'slicesX'), 'jpg', 'X')
                I.writeSlices(os.path.join(repDir, 'slicesY'), 'jpg', 'Y')
                I.writeSlices(os.path.join(repDir, 'slicesZ'), 'jpg', 'Z')

                if '_size' in itemDict: # write number of particles over a class image
                    text = itemDict['_size'] + " ptcls"
                    image = ImagePIL.open(os.path.join(repDir, 'slicesX_0000.jpg')).convert('RGB')
                    W, H = image.size
                    draw = ImageDraw.Draw(image)
                    draw.text((5, H - 15), text, fill=(0, 255, 0))
                    image.save(os.path.join(repDir, 'slicesX_0000.jpg'), quality=95)

                itemDict[self.ITEM_REPRESENTATION] = repDir

            elif isinstance(item, Volume):
                # Get all slices in x,y and z directions to represent the volume
                repDir = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.removeBaseExt(item.getFileName())))
                pwutils.makePath(repDir)
                if item.getFileName().endswith('.mrc'):
                    item.setFileName(item.getFileName() + ':mrc')
                I = emlib.Image(item.getFileName())
                I.writeSlices(os.path.join(repDir,'slicesX'), 'jpg', 'X')
                I.writeSlices(os.path.join(repDir, 'slicesY'), 'jpg', 'Y')
                I.writeSlices(os.path.join(repDir, 'slicesZ'), 'jpg', 'Z')

                itemDict[self.ITEM_REPRESENTATION] = repDir

            elif isinstance(item, Image):
                # use Location as item representation
                repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s_%s' % (self.outputName, item.getIndex(), pwutils.replaceBaseExt(item.getFileName(), 'jpg')))
                itemPath = item.getLocation()
                # apply a low pass filter
                args = " -i %s -o %s --fourier low_pass %f" % (itemPath[1], self._getTmpPath(os.path.basename(item.getFileName())), 0.05)
                getEnviron = Domain.importFromPlugin('xmipp3', 'Plugin', doRaise=True).getEnviron
                self.runJob('xmipp_transform_filter', args, env=getEnviron())

                self._ih.convert(self._getTmpPath(os.path.basename(item.getFileName())), os.path.join(self.getProject().path, repPath))
                itemDict[self.ITEM_REPRESENTATION] = repPath

            elif isinstance(item, CTFModel):
                # if exists use ctfmodel_quadrant as item representation, in other case use psdFile
                if item.hasAttribute('_xmipp_ctfmodel_quadrant'):
                    repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.replaceBaseExt(str(item._xmipp_ctfmodel_quadrant), 'jpg')))
                    itemPath = str(item._xmipp_ctfmodel_quadrant)

                else:
                    repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.replaceBaseExt(item.getPsdFile(), 'jpg')))
                    itemPath = item.getPsdFile()

                self._ih.convert(itemPath, os.path.join(self.getProject().path, repPath))
                itemDict[self.ITEM_REPRESENTATION] = repPath

            else:
                # in any other case look for a representation on attributes
                for key, value in attributes:
                    if os.path.exists(str(value)):
                        repPath = self.getTopLevelPath(self.DIR_IMAGES, '%s_%s' % (self.outputName, pwutils.replaceBaseExt(str(value), 'png')))
                        itemPath = str(value)
                        self._ih.convert(itemPath, os.path.join(self.getProject().path, repPath))
                        itemDict[self.ITEM_REPRESENTATION] = repPath
                        break

        except Exception as e:
            print("Cannot obtain item representation for %s" % str(itemPath))

        return itemDict