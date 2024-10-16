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
import subprocess
from pkg_resources import resource_filename
import jsonschema
from PIL import Image as ImagePIL
from PIL import ImageDraw
from empiar_depositor import empiar_depositor

from pyworkflow.protocol import params
from pyworkflow.object import String, Set
import pyworkflow.utils as pwutils
from pyworkflow.project import config
from pwem import Domain, emlib
from pwem.protocols import EMProtocol
from pwem.objects import (Class2D, Class3D, Image, CTFModel, Volume,
                          Micrograph, Movie, Particle, SetOfCoordinates, SetOfCTF, SetOfMicrographs, SetOfVolumes)
from pwem.viewers import EmPlotter
import emtable as md
from math import sqrt
import numpy as np
import shutil

from empiar import Plugin
from empiar.constants import *

DEPOSITION_TEMPLATE = resource_filename('empiar', '/'.join(('templates', 'empiar_deposition_template.json')))
DEPOSITION_SCHEMA = resource_filename('empiar_depositor', '/empiar_deposition.schema.json')
VIEWER_FILES = resource_filename('empiar', '/viewer_files')

VOXELTYPES = {
    emlib.DT_UCHAR: 'T1',  # 'UNSIGNED BYTE'
    emlib.DT_SCHAR: 'T2',  # 'SIGNED BYTE'
    emlib.DT_USHORT: 'T3',  # 'UNSIGNED 16 BIT INTEGER'
    emlib.DT_SHORT: 'T4',  # 'SIGNED 16 BIT INTEGER'
    emlib.DT_UINT: 'T5',  # 'UNSIGNED 32 BIT INTEGER'
    emlib.DT_INT: 'T6',  # 'SIGNED 32 BIT INTEGER'
    emlib.DT_FLOAT: 'T7',  # '32 BIT FLOAT'
    #'T8' - 'BIT',
    #'T9' - '4 BIT INTEGER',
    # 'OT' - other, in this case please specify the header format in the second element in capital letters.",
}

IMAGESETCATEGORIES = {
    "SetOfMicrographs": "T1",  # micrographs - single frame
    "SetOfMovies": 'T2',  # micrographs - multiframe
    # 'T3' : 'micrographs - focal pairs - unprocessed',
    # 'T4' : 'micrographs - focal pairs - contrast inverted',
    "SetOfMovieParticles": 'T5',  # : 'picked particles - single frame - unprocessed',
    # 'T6' : 'picked particles - multiframe - unprocessed',
    "SetOfParticles": 'T7',  # 'picked particles - single frame - processed',
    # "SetOfMovieParticles": 'T8',  # : 'picked particles - multiframe - processed',
    "SetOfAverages": 'T10',  # 'class averages',
    # 'T11' - 'stitched maps'
    # 'T12' - 'diffraction images'
    "SetOfVolumes": 'T13',  # 'reconstructed volumes',
    # 'OT' : 'other, in this case please specify the category in the second element.'
}

with pwutils.weakImport("tomo"):
    import tomo.objects
    IMAGESETCATEGORIES["SetOfTiltSeries"] = 'T9',  # : 'tilt series',
    IMAGESETCATEGORIES["SetOfSubTomograms"] = 'T14'  # 'subtomograms'


class EmpiarMappingError(Exception):
    """To raise it when we can't map Scipion data to EMPIAR data,
    e.g. we don't manage to assign an EMPIAR category to an image set."""
    pass


class EmpiarDepositor(EMProtocol):
    """
    Deposits image sets to EMPIAR.
    """
    _label = 'empiar deposition'
    _ih = emlib.image.ImageHandler()

    _workflowTemplate = {
        SCIPION_WORKFLOW: ""
    }

    _outputTemplate = {
        OUTPUT_NAME: ""
    }

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

    _grantOwnershipBasedOn = ['username', 'email', 'ORCiD']

    def __init__(self, **kwargs):
        EMProtocol.__init__(self, **kwargs)
        self.entryAuthorStr = ""
        self.workflowPath = String()
        self.depositionJsonPath = String()
        self.entryID = String()
        self.uniqueDir = String()

    # --------------- DEFINE param functions ----------------------------------

    def _defineParams(self, form):
        form.addSection(label='Entry')
        form.addParam("deposit", params.BooleanParam,
                      label="Make deposition", default=True,
                      help="Set to False to avoid performing a deposition to EMPIAR "
                           "(it will just be created locally).")
        form.addParam("viewer", params.BooleanParam,
                      label="Deploy workflow viewer locally", default=False,
                      help="Set to true to deploy the workflow viewer locally "
                           "(in http://localhost:<port chosen>) to understand how "
                           "it will look in EMPIAR.\nWhen you want to stop it, "
                           "you will have to do it manually by running in your "
                           "terminal something like: lsof -i tcp:<port chosen> | "
                           "awk 'NR > 1 {print $2}' | xargs kill")
        form.addParam("port", params.IntParam, label="Viewer port",
                      default=9000, condition="viewer",
                      help="The workflow web viewer will be deployed at this "
                           "port in your local machine. Choose an available one.")
        form.addParam("resume", params.BooleanParam,
                      label="Update existing entry", default=False,
                      condition='deposit',
                      help="Is this a continuation of a previous deposition?")
        form.addParam("submit", params.BooleanParam,
                      label="Submit", default=False, condition='deposit',
                      help="Is this the last entry update? If so, the EMPIAR "
                           "entry will be submitted and no future changes can "
                           "be done (except for providing the EMDB codes related "
                           "with the EMPIAR entry).")
        form.addParam('jsonTemplate', params.PathParam,
                      label="Custom json (Optional)", allowsNull=True,
                      help="Path to a customized template of the EMPIAR "
                           "submission json, if you don't want to use the "
                           "default one.")
        form.addParam('entryTopLevel', params.StringParam,
                      label="Top level folder",
                      validators=[params.NonEmpty], important=True,
                      help="How you want to name the top level folder of the "
                           "EMPIAR entry. \n This should be a "
                           "simple and descriptive name without special "
                           "characters (:,?, spaces, etc). ")
        form.addParam('entryTitle', params.StringParam,
                      label="Entry title", important=True,
                      help="EMPIAR entry title. This should not be empty "
                           "if not using a custom template.")
        form.addParam('entryAuthor', params.StringParam,
                      label="Entry author", important=True,
                      help='EMPIAR entry author in the form "LastName, '
                           'Initials" e.g. Smith, JW\nIf more than one author '
                           'is provided, put a semicolon between them. e.g. '
                           'Smith, JW; Winter, A\nThis should not be empty '
                           'if not using a custom template.')
        form.addParam('experimentType', params.EnumParam,
                      label="Experiment type",
                      choices=EXPERIMENTTYPES, default=2, important=True,
                      help="EMPIAR experiment type:\n"
                           "1 - image data collected using soft x-ray tomography\n"
                           "2 - simulated data, for instance, created using "
                           "InSilicoTEM\n(note: we only accept simulated data "
                           "in special circumstances such as test/training sets\n"
                           "for validation challenges: you need to ask for and "
                           "be granted permission PRIOR to deposition\n"
                           "otherwise the dataset will be rejected)\n"
                           "3 - raw image data relating to structures deposited "
                           "to the Electron Microscopy Data Bank\n"
                           "4 - image data collected using serial block-face "
                           "scanning electron microscopy\n(like the Gatan "
                           "3View system)\n"
                           "5 - image data collected using focused ion beam "
                           "scanning electron microscopy\n"
                           "6 - integrative hybrid modelling data\n"
                           "7 - correlative light-electron microscopy\n"
                           "8 - correlative light X-ray microscopy\n"
                           "9 - microcrystal electron diffraction\n"
                           "11 - ATUM-SEM\n"
                           "12 - Hard X-ray/X-ray microCT\n"
                           "13 - ssE")
        form.addParam('releaseDate', params.EnumParam, label="Release date",
                      choices=RELEASEDATETYPES, default=0, important=True,
                      help="EMPIAR release date:\n"
                           "Options for releasing entry to the public: \n"
                           "RE - directly after the submission has been processed\n"
                           "EP - after the related EMDB entry has been released\n"
                           "HP - after the related primary citation has been published\n"
                           "HO - delay release of entry by one year from the date of deposition"
                      )
        form.addParam('citationsBib', params.FileParam,
                      label='Citations bibtex',
                      help="File containing a bibtex with citations.")
        form.addParam('workflowHubURLs', params.StringParam,
                      label="WorkflowHub URL/DOI (Optional)", allowsNull=True,
                      help="If this analysis is based on a/several WorkflowHub "
                           "entry/ies you can provide the link/s separated by comma.")

        form.addSection(label='Image sets')
        self.inputSetsParam = form.addParam('inputSets', params.MultiPointerParam,
                                            label="Input set", important=True,
                                            pointerClass=','.join(IMAGESETCATEGORIES.keys()),
                                            minNumObjects=1,
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
                      help="Post or ZIP code. This should not be empty if "
                           "not using a custom template.")
        form.addParam('piTown', params.StringParam, label="Town or city",
                      help="Town or city name. This should not be empty if "
                           "not using a custom template.")
        form.addParam('piCountry', params.StringParam, label="Country",
                      help="Two letter country code eg. ES. This should "
                           "not be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(COUNTRYCODES))

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
                      help="Post or ZIP code. This should not be empty if "
                           "not using a custom template.")
        form.addParam('caTown', params.StringParam, label="Town or city",
                      help="Town or city name. This should not be empty if "
                           "not using a custom template.")
        form.addParam('caCountry', params.StringParam, label="Country",
                      help="Two letter country code e.g. ES. This should not "
                           "be empty if not using a custom template."
                           "\nValid country codes are %s" % " ".join(COUNTRYCODES))

        form.addSection(label="Transfer entry ownership")
        form.addParam("ownershipBasedOn", params.EnumParam, label="Based on",
                      choices=self._grantOwnershipBasedOn,
                      default=0, important=True,
                      help="You may want to transfer EMPIAR entry ownership to "
                           "other user. Here you specify if you are providing "
                           "the user username, email or ORCiD.")
        form.addParam("newOwnerId", params.StringParam,
                      label="User ID", important=True,
                      help="The user username, email or ORCiD.")

        form.addSection(label="EMDB codes (post-submission request)")
        form.addParam('EMDBrefs', params.StringParam, label="EMDB codes",
                      help="If you want to request to EMPIAR annotators to "
                           "update the EMPIAR entry (already submitted) with "
                           "the EMDB accesion codes, you can provide them here "
                           "separated by comma.")

    # --------------- INSERT steps functions ----------------------------------
    def _insertAllSteps(self):
        if self.EMDBrefs != '':
            self._insertFunctionStep(self.provideEMDBcodesStep)
        else:
            self._insertFunctionStep(self.createDepositionStep)
            if self.viewer:
                self._insertFunctionStep(self.deployWorkflowViewerStep)
            if self.deposit:
                self._insertFunctionStep(self.makeDepositionStep)

    # --------------- STEPS functions -----------------------------------------
    def createDepositionStep(self):
        # make folder in extra
        pwutils.makePath(self._getExtraPath(self.entryTopLevel.get()))
        pwutils.makePath(self.getTopLevelPath(DIR_IMAGES))

        # export workflow json
        self.exportWorkflow()

        # If deposition is not happening
        if not self.deposit:
            return
        # create deposition json
        jsonTemplatePath = self.jsonTemplate.get('').strip() or DEPOSITION_TEMPLATE

        authors = self.entryAuthor.get().split(';')
        self.entryAuthorStr = "["
        order_id = 0
        for author in authors:
            entryAuthorStr = author.split(',')
            self.entryAuthorStr += '%s{"name": "(\'%s\', \'%s\')", "order_id": %s, "author_orcid": null}' % (
                ',' if order_id > 0 else '', entryAuthorStr[0].strip(), entryAuthorStr[1].strip(), order_id)
            order_id += 1
        self.entryAuthorStr += "]"

        self.releaseDate = self.getEnumText('releaseDate')
        self.experimentType = self.experimentType.get() + 1

        with open(jsonTemplatePath, 'rb') as jsonTemplate:
            jsonStr = jsonTemplate.read().decode('utf-8')
            jsonStr = jsonStr % self.__dict__
            depoDict = json.loads(jsonStr)

        imageSets = self.processImageSets()
        if len(imageSets) > 0:
            self.debug("Imagesets is not empty")
            depoDict[IMGSET_KEY] = imageSets

        if self.citationsBib.get() is not None:
            with open(self.citationsBib.get(), "r") as file:
                citationJson = json.load(file)
                citationJson['editors'] = []
                depoDict['citation'][0] = citationJson

        depoDict[SCIPION_WORKFLOW_KEY] = self.getScipionWorkflow()
        depoJson = self.getTopLevelPath(OUTPUT_DEPO_JSON)
        with open(depoJson, 'w') as f:
            json.dump(depoDict, f, indent=4)
        self.depositionJsonPath.set(depoJson)
        self.info(f"Deposition JSON saved: {depoJson}")

        self._store()
        self.validateDepoJson(depoDict)

    def deployWorkflowViewerStep(self):
        viewerDir = self._getExtraPath(DIR_VIEWER)
        pwutils.makePath(viewerDir)

        cmd = [f"cd {viewerDir} &&"]
        # create links to static viewer files
        for fn in ['css', 'js', 'index.html', 'img', 'scipion-workflow.html']:
            cmd.append(f"ln -s {'/'.join([VIEWER_FILES, fn])} &&")
        # create links to 'workflow.json' file and 'images_representation' thumbnails folder
        cmd.append(f"ln -s {os.path.abspath(self.getTopLevelPath(DIR_IMAGES))} &&")
        cmd.append(f"ln -s {os.path.abspath(self.getTopLevelPath(OUTPUT_WORKFLOW))}")

        cmds = " ".join(cmd)
        subprocess.run(cmds, shell=True)

        # serve index.html
        existing_deployment = subprocess.run("lsof -i tcp:%s | awk 'NR > 1 {print $2}'" %
                                             self.port, shell=True, stdout=subprocess.PIPE)
        if existing_deployment.stdout.decode('utf-8') != '':
            subprocess.run("kill -9 %s" % existing_deployment.stdout.decode('utf-8'), shell=True)
        cmd = f"cd {viewerDir} && python3 -m http.server {self.port}"
        subprocess.Popen(cmd, shell=True)

        self.info(f"Workflow web viewer deployed at: http://localhost:{self.port}")

    def makeDepositionStep(self):
        depositorCall = '%(resume)s %(token)s %(depoJson)s %(ascp)s %(devel)s %(data)s -o %(submit)s %(grant)s'
        grantCall = "%(basedOn)s %(userID)s:1"
        grantArgs = {'basedOn': '-ge' if self.getEnumText('ownershipBasedOn') == 'email' else '-gu',
                     'userID': self.newOwnerId}
        args = {'resume': '-r %s %s' % (self.entryID, self.uniqueDir) if self.resume else "",
                'token': os.environ[EMPIAR_TOKEN],
                'depoJson': os.path.abspath(self.depositionJsonPath.get()),
                'ascp': '-a %s' % Plugin.getVar(ASCP_PATH),
                'devel': '-d' if os.environ.get(EMPIAR_DEVEL_MODE, False) else '',
                'data': os.path.abspath(self.getTopLevelPath()),
                'submit': '' if self.submit else '-s',
                'grant': grantCall % grantArgs if self.newOwnerId != '' else ''
                }

        depositorCall = depositorCall % args
        pwutils.yellow(f"Executing: empiar-depositor {depositorCall}")
        dep_result = empiar_depositor.main(depositorCall.split())
        if dep_result == 1:
            raise RuntimeError("Deposition failed, check the log files!")
        else:
            self.entryID.set(str(dep_result[0]))
            self.uniqueDir.set(dep_result[1])
            self._store()

    def provideEMDBcodesStep(self):
        # This function requests to EMPIAR annotators a post-submission change
        # for provide the EMDB entry/ies code/s related with the EMPIAR entry
        requests.packages.urllib3.disable_warnings()
        if os.environ.get(EMPIAR_DEVEL_MODE, False):
            url = 'https://wwwdev.ebi.ac.uk/pdbe/emdb/external_test/master/empiar/deposition/api/v1/request_changes/'
        else:
            url = 'https://www.ebi.ac.uk/pdbe/emdb/empiar/deposition/api/v1/request_changes/'

        data = {'entry_id': str(self.entryID),
                'msg': f'I would like to update this entry with the EMDB code/s: {self.EMDBrefs.get()}'
                }
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Token ' + os.environ[EMPIAR_TOKEN]}
        response = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        if response.status_code == 200:
            self.info('The request to EMPIAR annotators for adding the '
                      'EMDB entry/ies code/s was sent successfully')
        else:
            self.error('The request to EMPIAR annotators for adding the '
                       'EMDB entry/ies code/s was NOT successful')

    # --------------- INFO functions ------------------------------------------
    def _validate(self):
        errors = []
        if self.deposit:
            if Plugin.getVar(EMPIAR_TOKEN) is None:
                errors.append(f"Environment variable {EMPIAR_TOKEN} not set.")

            if Plugin.getVar(ASPERA_PASS) is None:
                errors.append(f"Environment variable {ASPERA_PASS} not set.")

            if not os.path.exists(Plugin.getVar(ASCP_PATH)):
                errors.append(f"Variable {ASCP_PATH} points to "
                              f"{Plugin.getVar(ASCP_PATH)} (aspera client) but "
                              "it does not exist.")

            if errors:
                errors.append(f"Please review the setup section at {Plugin.getUrl()}")

        return errors

    def _citations(self):
        return ['Iudin2016']

    def _summary(self):
        summary = []
        if self.depositionJsonPath.get():
            summary.append('Generated deposition files:')
            summary.append(f'- [[{self.workflowPath}][Scipion workflow]]')
            summary.append(f'- [[{self.depositionJsonPath}][Deposition json]]')
        else:
            summary.append('No deposition files generated yet')

        return summary

    def _methods(self):
        return []

    # -------------------- UTILS functions ------------------------------------

    def getTopLevelPath(self, *paths):
        return self._getExtraPath(self.entryTopLevel.get(), *paths)

    def getProjectPath(self, *paths):
        return self.getProject().getPath(*paths)

    def exportWorkflow(self):
        project = self.getProject()
        workflowProts = project.getRuns()
        # workflow prots are all prots if no json provided
        workflowJsonPath = self.getProjectPath(self.getTopLevelPath(OUTPUT_WORKFLOW))
        protDicts = project.getProtocolsDict(workflowProts)

        # labels and colors
        settingsPath = self.getProjectPath(project.settingsPath)
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

        # Add extra info to protocolsDict
        for prot in workflowProts:
            objId = prot.getObjId()
            # Get summary and add input and output information
            summary = prot.summary()
            for a, item in prot.iterInputAttributes():
                if item.isPointer():
                    try:
                        inputLabel = protDicts[int(item.getUniqueId().split('.')[0])]['object.label']
                        inputLabel = f" (from {inputLabel}) "
                    except:
                        inputLabel = ''
                itemName = item.getUniqueId() if item.isPointer() else item.getObjName()
                summary.append(f"Input: {itemName}{inputLabel} - {str(item.get())}")

            protDicts[objId]['output'] = []

            for a, output in prot.iterOutputAttributes():
                protDicts[objId]['output'].append(self.getOutputDict(output))
                summary.append(f"Output: {output.getObjName()} - {str(output)}")

            # additional plots
            additionalPlots = self.getAdditionalPlots(prot)
            for plotName, plotPath in additionalPlots.items():
                protDicts[objId]['output'].append({OUTPUT_NAME: plotName,
                                                   OUTPUT_ITEMS: [{ITEM_REPRESENTATION: plotPath}]})

            protDicts[objId]['summary'] = '\n'.join(summary)

            # Get log (stdout)
            outputs = []
            stdout = prot.getStdoutLog()
            if pwutils.exists(stdout):
                logPath = self.getTopLevelPath(DIR_IMAGES,
                                               "%s_%s.log" % (objId, prot.getClassName()))
                pwutils.copyFile(stdout, logPath)
                outputs = logPath

            protDicts[objId]['log'] = outputs

            # labels
            if objId in protsLabelsDict.keys():
                protDicts[objId]['label'] = protsLabelsDict[objId]
                protDicts[objId]['labelColor'] = []
                for label in protDicts[objId]['label']:
                    protDicts[objId]['labelColor'].append(labelsDict[label])

            # Get plugin and binary version
            try:
                protDicts[objId]['plugin'] = prot.getPlugin().getName()
                package = self.getClassPackage()
                if hasattr(package, "__version__"):
                    protDicts[objId]['pluginVersion'] = package.__version__
                protDicts[objId]['pluginBinaryVersion'] = prot.getPlugin().getActiveVersion()
            except:
                pass

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
        self.info(f"Workflow JSON saved: {workflowJsonPath}")

    def validateDepoJson(self, depoDict):
        with open(DEPOSITION_SCHEMA) as f:
            schema = json.load(f)

        jsonschema.validate(depoDict, schema)  # raises exception if not valid

    # --------------- imageSet utils -------------------------
    def getEmpiarCategory(self, imageSet):
        className = imageSet.getClassName()
        category = IMAGESETCATEGORIES.get(className, None)
        if category is None:
            raise EmpiarMappingError('Could not assign an EMPIAR '
                                     f'category to image set {imageSet.getObjName()}')
        else:
            return category, ''

    def getEmpiarFormat(self, imagePath):
        ext = pwutils.getExt(imagePath).lower().strip('.')
        imgFormat = IMAGESETFORMATS.get(ext, None)
        if imgFormat is None:
            raise EmpiarMappingError(f'Image format not recognized: {ext}')
        else:
            return imgFormat, ''

    def getVoxelType(self, imageObj):
        dataType = self._ih.getDataType(imageObj)
        empiarType = VOXELTYPES.get(dataType, None)
        if empiarType is None:
            raise EmpiarMappingError('Could not map voxel type for '
                                     f'image {imageObj.getFilename()}')
        else:
            return empiarType, ''

    def getImageSetDict(self, imageSet):
        firstImg = imageSet.getFirstItem()
        firstFileName = firstImg.getFileName()
        dims = imageSet.getDimensions()
        micSetDict = copy.deepcopy(self._imageSetTemplate)
        micSetDict[IMGSET_NAME] = imageSet.getObjName()
        micSetDict[IMGSET_DIR] = "%s/%s/%s" % (ENTRY_DIR, self.entryTopLevel.get(), micSetDict[IMGSET_NAME])
        micSetDict[IMGSET_CAT] = "('%s', '%s')" % self.getEmpiarCategory(imageSet)
        micSetDict[IMGSET_DATA_FORMAT] = "('%s', '%s')" % self.getEmpiarFormat(firstFileName)
        micSetDict[IMGSET_HEADER_FORMAT] = micSetDict[IMGSET_DATA_FORMAT]
        micSetDict[IMGSET_SIZE] = len(imageSet)
        micSetDict[IMGSET_FRAMES] = dims[2]
        micSetDict[IMGSET_VOXEL_TYPE] = "('%s', '%s')" % self.getVoxelType(firstImg)
        micSetDict[IMGSET_PIXEL_WIDTH] = imageSet.getSamplingRate()
        micSetDict[IMGSET_PIXEL_HEIGHT] = micSetDict[IMGSET_PIXEL_WIDTH]
        micSetDict[IMGSET_WIDTH] = dims[0]
        micSetDict[IMGSET_HEIGHT] = dims[1]
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
        workflowDict[SCIPION_WORKFLOW] = "%s/%s/%s" % (ENTRY_DIR,
                                                       self.entryTopLevel.get(),
                                                       os.path.basename(self.workflowPath.get()))
        return workflowDict

    def getOutputDict(self, output):
        self.outputName = output.getObjName()
        outputDict = {
            OUTPUT_NAME: output.getObjName(),
            OUTPUT_TYPE: output.getClassName()
        }
        items = []

        # If output is a Set get a list with all items
        if isinstance(output, Set):
            outputDict[OUTPUT_SIZE] = output.getSize()
            count = 0
            if isinstance(output, SetOfCoordinates):
                coordinatesDict = {}
                for micrograph in output.getMicrographs():  # get the first three micrographs
                    micFn = micrograph.getFileName()
                    count += 1
                    repPath = self.getTopLevelPath(DIR_IMAGES, '%s_%s' % (
                        self.outputName, pwutils.replaceBaseExt(micFn, 'jpg')))
                    self.createThumbnail(micFn, repPath, type=Micrograph)
                    coordinatesDict[micrograph.getMicName()] = {'path': repPath,
                                                                'Xdim': micrograph.getXDim(),
                                                                'Ydim': micrograph.getYDim()}

                    items.append({ITEM_REPRESENTATION: repPath})
                    if count == 3:
                        break

                for coordinate in output:  #  for each micrograph, get its coordinates
                    if coordinate.getMicName() in coordinatesDict:
                        coordinatesDict[coordinate.getMicName()].setdefault('coords', []).append(
                            [coordinate.getX(), coordinate.getY()])

                for micrograph, values in coordinatesDict.items():  # draw coordinates in micrographs jpgs
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
                    count += 1
                    itemDict = self.getItemDict(item, count)
                    items.append(itemDict)
                    # In some types get only a limited number of items
                    if (isinstance(item, Micrograph) or
                        isinstance(item, Movie) or
                        isinstance(item, CTFModel)) and count == 3:
                        break
                    if isinstance(item, Particle) and count == 15:
                        break

        # If it is a single object then only one item is present
        else:
            items.append(self.getItemDict(output))

        outputDict[OUTPUT_ITEMS] = items

        return outputDict

    def getItemDict(self, item, count=None):
        attributes = item.getAttributes()
        # Skip attributes that are Pointer
        itemDict = {k: str(v) for k, v in attributes if not v.isPointer()}
        itemDict[ITEM_ID] = item.getObjId()

        try:
            # Get item representation
            if isinstance(item, Class2D):
                # use representative as item representation
                rep = item.getRepresentative()
                repPath = self.getTopLevelPath(DIR_IMAGES, '%s_%s_%s' % (
                    self.outputName, rep.getIndex(),
                    pwutils.replaceBaseExt(rep.getFileName(), 'jpg')))
                self._ih.convert(rep.getLocation(), self.getProjectPath(repPath))

                if '_size' in itemDict:  # write number of particles over the class
                    text = itemDict['_size'] + " ptcls"
                    image = ImagePIL.open(repPath).convert('RGB')
                    W, H = image.size
                    draw = ImageDraw.Draw(image)
                    draw.text((5, H - 15), text, fill=(0, 255, 0))
                    image.save(repPath, quality=95)

                itemDict[ITEM_REPRESENTATION] = repPath

            elif isinstance(item, Class3D):
                itemFn = item.getFileName()
                # Get all slices in x,y and z directions of representative to represent the class
                rep = item.getRepresentative()
                repDir = self.getTopLevelPath(DIR_IMAGES,
                                              '%s_%s' % (self.outputName,
                                                         pwutils.removeBaseExt(rep.getFileName())))
                pwutils.makePath(repDir)
                if itemFn.endswith('.mrc'):
                    item.setFileName(itemFn + ':mrc')
                V = emlib.Image(rep.getFileName()).getData()
                self.writeSlices(V, os.path.join(repDir, 'slicesX'), 'X')
                self.writeSlices(V, os.path.join(repDir, 'slicesY'), 'Y')
                self.writeSlices(V, os.path.join(repDir, 'slicesZ'), 'Z')

                if '_size' in itemDict:  # write number of particles over a class image
                    text = itemDict['_size'] + " ptcls"
                    image = ImagePIL.open(os.path.join(repDir, 'slicesX_0000.jpg')).convert('RGB')
                    W, H = image.size
                    draw = ImageDraw.Draw(image)
                    draw.text((5, H - 15), text, fill=(0, 255, 0))
                    image.save(os.path.join(repDir, 'slicesX_0000.jpg'), quality=95)

                itemDict[ITEM_REPRESENTATION] = [os.path.join(repDir, file) for file in sorted(os.listdir(repDir))]

            elif isinstance(item, Volume):
                itemFn = item.getFileName()
                # if is a .vol volume, convert to .mrc
                if itemFn.endswith(".vol"):
                    repPath = self.getTopLevelPath(DIR_IMAGES,
                                                   f"{self.outputName}_{pwutils.removeBaseExt(itemFn)}.mrc")
                    self._ih.convert(itemFn, self.getProjectPath(repPath))

                # Get all slices in x,y and z directions to represent the volume
                repDir = self.getTopLevelPath(DIR_IMAGES,
                                              f"{self.outputName}_{pwutils.removeBaseExt(itemFn)}")
                pwutils.makePath(repDir)
                if itemFn.endswith('.mrc'):
                    item.setFileName(itemFn + ':mrc')
                V = emlib.Image(itemFn).getData()
                self.writeSlices(V, os.path.join(repDir, 'slicesX'), 'X')
                self.writeSlices(V, os.path.join(repDir, 'slicesY'), 'Y')
                self.writeSlices(V, os.path.join(repDir, 'slicesZ'), 'Z')

                itemDict[ITEM_REPRESENTATION] = [os.path.join(repDir, file) for file in sorted(os.listdir(repDir))]

            elif isinstance(item, Image):
                itemFn = item.getFileName()
                # use Location as item representation
                repPath = self.getTopLevelPath(DIR_IMAGES,
                                               '%s_%s_%s' % (self.outputName,
                                                             item.getIndex(),
                                                             pwutils.replaceBaseExt(itemFn, 'jpg')))
                self.createThumbnail(itemFn, repPath,
                                     Micrograph if isinstance(item, Micrograph) else Particle if isinstance(item, Particle) else None,
                                     count)
                itemDict[ITEM_REPRESENTATION] = repPath

            elif isinstance(item, CTFModel):
                # if exists use ctfmodel_quadrant as item representation, in other case use psdFile
                if item.hasAttribute('_xmipp_ctfmodel_quadrant'):
                    itemPath = str(item._xmipp_ctfmodel_quadrant)
                    repPath = self.getTopLevelPath(DIR_IMAGES,
                                                   '%s_%s' % (self.outputName,
                                                              pwutils.replaceBaseExt(itemPath, 'jpg')))

                    self._ih.convert(itemPath, self.getProjectPath(repPath))
                else:
                    itemPath = item.getPsdFile()
                    repPath = self.getTopLevelPath(DIR_IMAGES,
                                                   '%s_%s' % (self.outputName,
                                                              pwutils.replaceBaseExt(itemPath, 'jpg')))

                    image = emlib.Image(itemPath)
                    data = image.getData()

                    GAMMA = 2.2 # apply a gamma correction
                    data = data ** (1/GAMMA)
                    data = np.fft.fftshift(data)

                    image.setData(data)
                    image.write(repPath)

                itemDict[ITEM_REPRESENTATION] = repPath

            else:
                # in any other case look for a representation on attributes
                for key, value in attributes:
                    itemPath = str(value)
                    if os.path.exists(itemPath):
                        repPath = self.getTopLevelPath(DIR_IMAGES,
                                                       '%s_%s' % (self.outputName,
                                                                  pwutils.replaceBaseExt(itemPath, 'png')))
                        self._ih.convert(itemPath, self.getProjectPath(repPath))
                        itemDict[ITEM_REPRESENTATION] = repPath
                        break

        except Exception as e:
            self.error(f"Cannot obtain item representation for {str(item)}: {e}")

        return itemDict

    def createThumbnail(self, inputFn, outputFn, type, count=None):
        """ Apply a low pass filter and make a jpg thumbnail. """
        outputFn = self.getProjectPath(outputFn)
        # if inputFn.endswith('.stk'):
        #     self._ih.convert(inputFn, outputFn)
        x, y, z, n = self._ih.getDimensions(inputFn)
        getEnviron = Domain.importFromPlugin('xmipp3', 'Plugin', doRaise=True).getEnviron
        if type == Particle:
            args = f" -i {inputFn if n == 1 else f'{count}@{inputFn}'} -o {outputFn}"
            self.runJob('xmipp_image_convert', args, env=getEnviron())
        elif type == Micrograph:
            args = f" -i {inputFn if n == 1 else f'{count}@{inputFn}'} -o {outputFn} --fourier low_pass 0.05"
            self.runJob('xmipp_transform_filter', args, env=getEnviron())

    def getAdditionalPlots(self, prot):
        """ Generate additional plots apart from basic thumbnails. """
        def getMRCVolume(output, outputName):
            itemFn = output.getFileName()
            if itemFn.endswith('mrc'):
                itemFn = itemFn.replace(':mrc', '')
                repPath = self.getTopLevelPath(DIR_IMAGES,
                                               f"{outputName}_{pwutils.removeBaseExt(itemFn)}.mrc")
                shutil.copy(itemFn, repPath)
            if itemFn.endswith('.map'):
                repPath = self.getTopLevelPath(DIR_IMAGES,
                                               f"{outputName}_{pwutils.removeBaseExt(itemFn)}.map")
                shutil.copy(itemFn, repPath)
            if itemFn.endswith('.vol'): # already copied (because it was previously converted to mrc)
                repPath = self.getTopLevelPath(DIR_IMAGES,
                                               f"{outputName}_{pwutils.removeBaseExt(itemFn)}.mrc")
            return f"{outputName}_{pwutils.removeBaseExt(itemFn)}_3D", repPath

        plotPaths = {}
        for a, output in prot.iterOutputAttributes():
            # alignment methods
            if isinstance(output, SetOfMicrographs):
                shiftsX, shiftsY, totalShifts = [], [], []
                for item in output.iterItems():
                    # XmippProtFlexAlign, XmippProtMovieMaxShift...
                    if item.hasAttribute('_xmipp_ShiftX') and item.hasAttribute('_xmipp_ShiftY'):
                        shiftsX = [float(x) for x in item.getAttributeValue('_xmipp_ShiftX').split(',')]
                        shiftsY = [float(y) for y in item.getAttributeValue('_xmipp_ShiftY').split(',')]

                    # ProtRelionMotioncor
                    elif os.path.exists(os.path.join(prot._getExtraPath(), pwutils.replaceBaseExt(item.getMicName(), 'star'))):
                        starFile = os.path.join(prot._getExtraPath(), pwutils.replaceBaseExt(item.getMicName(), 'star'))
                        table = md.Table(fileName=starFile, tableName='global_shift')

                        for i, row in enumerate(table):
                            shiftsX.append(float(row.rlnMicrographShiftX))
                            shiftsY.append(float(row.rlnMicrographShiftY))

                    if len(shiftsX) > 0 and len(shiftsY) > 0:
                        # relative shifts
                        relativeShiftsX = [shiftsX[i] - shiftsX[i-1] for i in range(1, len(shiftsX))]
                        relativeShiftsY = [shiftsY[i] - shiftsY[i-1] for i in range(1, len(shiftsY))]

                        totalShifts.append(sqrt(sum((x**2 + y**2) for x, y in zip(relativeShiftsX, relativeShiftsY))))

                        numberOfBins = 10
                        plotterShifts = EmPlotter()
                        plotterShifts.createSubPlot("Total shifts histogram", "Drift (pixels)", "#")
                        plotterShifts.plotHist(totalShifts, nbins=numberOfBins)
                        repPath = self.getTopLevelPath(DIR_IMAGES, f'{output.getObjName()}_shifts_histogram.jpg')
                        plotterShifts.savefig(os.path.join(self.getProject().path, repPath))
                        plotterShifts.close()
                        plotPaths[f'{output.getObjName()}_shifts_histogram'] = repPath

            # CTF methods
            if isinstance(output, SetOfCTF):
                defocusU = [ctf.getDefocusU() for ctf in output]
                defocusV = [ctf.getDefocusV() for ctf in output]
                defocus = [(defU + defV)/2 for defU, defV in zip(defocusU, defocusV)]
                astigmatism = [abs(defU - defV)/2 for defU, defV in zip(defocusU, defocusV)]

                numberOfBins = 10
                plotterDefocus = EmPlotter()
                plotterAstigmatism = EmPlotter()

                plotterDefocus.createSubPlot("Defocus histogram", "Defocus (A)", "#")
                plotterDefocus.plotHist(defocus, nbins=numberOfBins)
                repPath = self.getTopLevelPath(DIR_IMAGES, f'{output.getObjName()}_defocus_histogram.jpg')
                plotterDefocus.savefig(os.path.join(self.getProject().path, repPath))
                plotterDefocus.close()
                plotPaths[f'{output.getObjName()}_defocus_histogram'] = repPath

                plotterAstigmatism.createSubPlot("Astigmatism histogram", "Astigmatism (A)", "#")
                plotterAstigmatism.plotHist(astigmatism, nbins=numberOfBins)
                repPath = self.getTopLevelPath(DIR_IMAGES, f'{output.getObjName()}_defocus_astigmatism.jpg')
                plotterAstigmatism.savefig(os.path.join(self.getProject().path, repPath))
                plotterAstigmatism.close()
                plotPaths[f'{output.getObjName()}_defocus_astigmatism.jpg'] = repPath

            # Volumes
            if isinstance(output, Volume):
                name, repPath = getMRCVolume(output, output.getObjName())
                plotPaths[name] = repPath

            elif isinstance(output, SetOfVolumes):
                for item in output.iterItems():
                    name, repPath = getMRCVolume(item, output.getObjName())
                    plotPaths[name] = repPath

        return plotPaths

    def writeSlices(self, V, fnRoot, direction):
        """ Generate volume slices for x, y and z axis. """
        V = np.squeeze(V) # for volumes with numpy arrays with 4 dims
        m = np.min(V)
        M = np.max(V)
        V = (V - m) / (M - m) * 255
        Zdim, Ydim, Xdim = V.shape
        if direction == 'X':
            for j in range(Xdim):
                I = ImagePIL.fromarray(np.reshape(V[:, :, j], [Zdim, Ydim]).astype(np.uint8))
                I.save(f'{fnRoot}_{"{:04d}".format(j)}.jpg')
        if direction == 'Y':
            for i in range(Ydim):
                I = ImagePIL.fromarray(np.reshape(V[:, i, :], [Zdim, Xdim]).astype(np.uint8))
                I.save(f'{fnRoot}_{"{:04d}".format(i)}.jpg')
        if direction == 'Z':
            for k in range(Zdim):
                I = ImagePIL.fromarray(np.reshape(V[k, :, :], [Ydim, Xdim]).astype(np.uint8))
                I.save(f'{fnRoot}_{"{:04d}".format(k)}.jpg')
