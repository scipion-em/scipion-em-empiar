
# **************************************************************************
# *
# * Authors:    Yunior C. Fonseca Reyna (cfonseca@cnb.csic.es)
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

from enum import IntEnum
from pwem import emlib

EMPIAR_HOME = 'EMPIAR_HOME'

ASCP_PATH = "ASCP"
ASPERA_PASS = "ASPERA_SCP_PASS"
EMPIAR_TOKEN = "EMPIAR_TOKEN"
EMPIAR_DEVEL_MODE = "EMPIAR_DEVEL_MODE"


# Protocols constants below
class DataFormat(IntEnum):
    NONE = 0
    MRC = 1
    MRCS = 2
    TIFF = 3
    DM4 = 4
    HDF5 = 5
    EER = 6


IMAGESETCATEGORIES = {
    "SetOfMicrographs": "T1",  # micrographs - single frame
    "SetOfMovies": 'T2',  # micrographs - multiframe
    # 'T3' : 'micrographs - focal pairs - unprocessed',
    # 'T4' : 'micrographs - focal pairs - contrast inverted',
    "SetOfMovieParticles": 'T5',  # : 'picked particles - single frame - unprocessed',
    # 'T6' : 'picked particles - multiframe - unprocessed',
    "SetOfParticles": 'T7',  # 'picked particles - single frame - processed',
    # "SetOfMovieParticles": 'T8',  # : 'picked particles - multiframe - processed',
    "SetOfTiltSeries": 'T9',  # : 'tilt series',
    "SetOfAverages": 'T10',  # 'class averages',
    # 'T11' - 'stitched maps'
    # 'T12' - 'diffraction images'
    "SetOfVolumes": 'T13',  # 'reconstructed volumes',
    "SetOfSubtomograms": 'T14'  # 'subtomograms'
    # 'OT' : 'other, in this case please specify the category in the second element.'
}
IMAGESETFORMATS = {
    'mrc': 'T1',
    'mrcs': 'T2',
    'tiff': 'T3',
    'img': 'T4',  # imagic
    'dm3': 'T5',
    'dm4': 'T6',
    'spi': 'T7',  # spider
    'xml': 'T8',
    'eer': 'T9',
    'png': 'T10',
    'jpeg': 'T11',
    'smv': 'T12',
    'em': 'T13',
    'tpx3': 'T14'
}

EXPERIMENTTYPES = ['1','2','3','4','5','6','7','8','9','11','12','13']
RELEASEDATETYPES = ["RE", "EP", "HP", "HO"]

COUNTRYCODES = ['AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU',
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

OUTPUT_NAME = 'outputName'
OUTPUT_TYPE = 'outputType'
OUTPUT_ITEMS = 'outputItems'
OUTPUT_SIZE = 'outputSize'
OUTPUT_DEPO_JSON = 'deposition.json'
OUTPUT_WORKFLOW = 'workflow.json'

ITEM_ID = 'item_id'
ITEM_REPRESENTATION = 'item_representation'

DIR_IMAGES = 'images_representation'
DIR_VIEWER = 'web-workflow-viewer'

SCIPION_WORKFLOW_KEY = 'workflow_file'
SCIPION_WORKFLOW = 'path'
