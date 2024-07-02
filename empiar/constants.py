
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
