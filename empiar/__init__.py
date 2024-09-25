# **************************************************************************
# *
# * Authors:     Yaiza Rancel (cyrancel@cnb.csic.es)
# *              Yunior C. Fonseca Reyna (cfonseca@cnb.csic.es)
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
import pwem

from empiar.constants import ASPERA_PASS, ASCP_PATH, EMPIAR_TOKEN


__version__ = '3.1'
_references = ['Iudin2016']
_logo = 'EMPIAR_logo.png'


class Plugin(pwem.Plugin):
    _pathVars = []
    _url = "https://github.com/scipion-em/scipion-em-empiar"

    @classmethod
    def _defineVariables(cls):
        cls._defineVar(ASCP_PATH, os.path.expanduser('~/.aspera/connect/bin/ascp'))
        cls._defineVar(ASPERA_PASS, '')
        cls._defineVar(EMPIAR_TOKEN, '')

    @classmethod
    def defineBinaries(cls, env):
        empiar_cmd = [('./ibm-aspera-connect_4.2.12.780_linux_x86_64.tar.gz', [])]
        # url = 'https://d3gcli72yxqn2z.cloudfront.net/downloads/connect/latest/bin/ibm-aspera-connect_4.2.11.768_linux_x86_64.tar.gz'
        url = 'https://d3gcli72yxqn2z.cloudfront.net/downloads/connect/latest/bin/ibm-aspera-connect_4.2.12.780_linux_x86_64.tar.gz'
        env.addPackage('ascp', version="4.2.12",
                       url=url,
                       default=True,
                       buildDir='ascp',
                       createBuildDir=True,
                       target='ascp/ibm-aspera-connect_4.2.12.780_linux_x86_64.tar.gz',
                       commands=empiar_cmd)
