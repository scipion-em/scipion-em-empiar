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

from .constants import *


__version__ = '3.0.4'
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
        empiar_cmd = [('./aspera-connect-3.7.4.147727-linux-64.sh',
                      [cls.getVar(ASCP_PATH)])]
        url = 'https://download.asperasoft.com/download/sw/connect/3.7.4/aspera-connect-3.7.4.147727-linux-64.tar.gz'
        env.addPackage('ascp', version="3.7.4",
                       url=url,
                       default=True,
                       buildDir='ascp',
                       createBuildDir=True,
                       target='ascp/aspera-connect-3.7.4.147727-linux-64.sh',
                       commands=empiar_cmd)
