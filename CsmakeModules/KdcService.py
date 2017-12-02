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
from Csmake.CsmakeAspect import CsmakeAspect
from CsmakeKerberosProvider.KdcServiceProvider import KdcServiceProvider

class KdcService(CsmakeAspect):
    """Purpose: Provide a local kdc configuration that simulates
                a network interaction with a kdc
     Options:
         interfaces - (OPTIONAL) List of interfaces to listen on,
                        delimited with commas or newlines.
                      Default: localhost
         tag - (OPTIONAL) allows for several sshd services to be
                          operational at the same time in the same build
                          given unique values for 'tag'
                      Default: <nothing>
         chroot - (OPTIONAL) Will operate the sshd in a chrooted environment
                          determined by the path provided
                    Default: /
                  Note: This will temporarily change the specified
                      user's .ssh/config file in the specified environment
                      (unless client-chroot is specified)
         config-path - (OPTIONAL) Will set the given path as the location for
                                  configs.  It will attempt to delete
                                  all the files it creates in the given
                                  path.  This path will be created if it does
                                  not exist.  If the path contains no files
                                  when the service ends, the path will also
                                  be removed.
                       Default: A temporary directory will be used
         change-env-vars - (OPTIONAL) 'True' allows the setup to change the
                 current csmake and child execution environment variables.
                 Specifically: KRB_KDC_PROFILE, KRB5_TRACE, KRB5_CONFIG
         config-dir-env - (OPTIONAL) Set the given csmake environment name
                 to the section's config directory.
                 Default: csmake's environment does not change.
         principals - (OPTIONAL) Adds the given principals to the
                 kdc for access. (Newline or comma delimited)
                 The principal may be expressed with or without a password
                 using a colon ':', e.g., myprinc:<password>.  The default
                 password is 'csmake'.
                 Default: No principals (other than K/M) are created.
                 KdcAddPrincipal and KdcDeletePrincipal can be used
                 to manipulate the principals while it is active.
         realm - (OPTIONAL) Specifies the realm to establish with the kdc
                 Default: CSMAKE.DOMAIN
         port - (OPTIONAL) Will stand up the sshd on the given port
                 Default: a currently open port in 'port-range'
         port-range - (OPTIONAL) Will stand up the sshd in a given range
                   Ignored if a specific port is called out by 'port'
                   Format:  <lower> - <upper> (Inclusive)
                   Default: 2222-3333
     Phases/JoinPoints:  
         build, test - will stand the service up in the build phase
                 When used as a regular section, StopKdcService must be used
         start__build, start__test 
                     - will stand up the service at the start of the
                        decorated regular section
         end__build, end__test
                     - will tear down the service at the end of the section
    """

    def _startService(self, options):
        if KdcServiceProvider.hasServiceProvider(self.tag):
            self.log.error("kdc with service tag '%s' already executing", self.tag)
            self.log.failed()
            self._unregisterOnExitCallback("_stopService")
            return None

        self.provider = KdcServiceProvider.createServiceProvider(
            self.tag,
            self,
            **options)
        self.provider.startService()
        if self.provider is not None and self.provider.isServiceExecuting():
            self.log.passed()
        else:
            self.log.error("The kdc service could not be started")
            self.log.failed()
            self._unregisterOnExitCallback("_stopService")
        return None

    def _stopService(self):
        KdcServiceProvider.disposeServiceProvider(self.tag)
        self._unregisterOnExitCallback("_stopService")
        self.log.passed()

    def build(self, options):
        self.tag = '_'
        if 'tag' in options:
            self.tag = options['tag']
            del options['tag']
        self._dontValidateFiles()
        self._registerOnExitCallback("_stopService")
        self.log.passed()
        return self._startService(options)

    def test(self, options):
        return self.build(options)

    def start__build(self, phase, options, step, stepoptions):
        return self.build(options)

    def end__build(self, phase, options, step, stepoptions):
        self._stopService()

    def start__test(self, phase, options, step, stepoptions):
        return self.start__build(phase, options, step, stepoptions)

    def end__test(self, phase, options, step, stepoptions):
        return self.end__build(phase, options, step, stepoptions)
