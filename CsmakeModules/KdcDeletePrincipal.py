# <copyright>
# (c) Copyright 2017 Cardinal Peak Technologies
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
from CsmakeKerberosProvider.KdcServiceProvider import KdcServiceProvider
from Csmake.CsmakeModule import CsmakeModule

class KdcDeletePrincipal(CsmakeModule):
    """Purpose: A module to delete a principal frome the given kdc
               (by the tag provided)
       Flags: tag - (OPTIONAL) The tag of the kdc service to modify
                     Default is the default kdc
              principals - Principals to delete from the realm of csmake's kdc
       Phases: build, test
    """

    REQUIRED_OPTIONS=['principals']

    def build(self, options):
        self.tag = '_'
        if 'tag' in options:
            self.tag = options['tag']
        service = KdcProvider.getServiceProvider(self.tag)
        principals = self._parseCommaAndNewlineList(options['principals'])
        for principal in principals:
            service.deletePrincipal(principal)
        self.log.passed()
        return True

    def test(self, options):
        return self.build(options)
