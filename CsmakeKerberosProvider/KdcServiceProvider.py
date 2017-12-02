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
import threading
import subprocess
import os.path
import tempfile
import time
from CsmakeProviders.CsmakeServiceProvider import CsmakeServiceProvider
from CsmakeProviders.CsmakeServiceProvider import CsmakeServiceDaemon
from CsmakeProviders.CsmakeServiceProvider import CsmakeServiceConfigManager
from CsmakeProviders.CsmakeServiceProvider import CsmakeServiceConfig

class KdcConfigurationHelper:
    @staticmethod
    def kdcDebugLevel(settings):
        #TODO: Change the settings here, kdc.conf has logging settings
        loglevel = 'ERROR'
        if settings['quiet']:
            loglevel = 'QUIET'
        else:
            if settings['verbose']:
                loglevel = 'VERBOSE'
            if settings['debug']:
                loglevel = 'DEBUG'
            if settings['dev-output']:
                loglevel = 'DEBUG3'
        return loglevel

    @classmethod
    def kdb_util_command(clazz):
        #TODO: We may actually need this in the Config objects
        fullkdb5util = self.configManager.shellout(
            subprocess.check_output,
            ['which', 'kdb5_util'] ).strip()

#Need:
# - principal database (setting goes into kdc.conf) -d dbfile for kdb5_util
# - stash file (key_stash_file in kdc.conf) -sf stash_file
#
# Steps:
# - create a database:
#   kdb5_util -sf <stashfile> -d <dbfile> -k RC4-HMAC  -P <master pass> -r <realm> create -s
#   Working Example:
#     kdb5_util -k RC4-HMAC -P "ABS" -sf test.krbdb.stash -d test.krbdb -r AAA.YYY create -s
#   Files:
#       test.krbdb        test.krbdb.kadm5.lock  test.krbdb.ok
#       test.krbdb.kadm5  test.krbdb.kdc.conf    test.krbdb.stash
#   NOTE: Can be managed from a single directory
# - create principals, you have to have KRB5_KDC_PROFILE set to a file that
#   looks like (from the example above):
#   [realms]
#   AAA.YYY = {
#       database_name = /home/jpatterson/kerb_kdc_testing/test.krbdb
#       key_stash_file = /home/jpatterson/kerb_kdc_testing/test.krbdb.stash
#       supported_enctypes = RC4-HMAC
#   }
#   kadmin.local -r <realm> -p K/M -q "<command to do>"
#       K/M is the default master principal
#   Working Example:
#     kadmin.local -r AAA.YYY -p K/M
class KdcClientConfig(CsmakeServiceConfig):
    CONFIG_FILE_NAME = "csmake.krb5.conf"

    def ensure(self):
        pathToConfig = os.path.join(
            self.path,
            self.CONFIG_FILE_NAME )
        self.log.debug("Writing config to: %s", pathToConfig)
        self._backupAndSetup(pathToConfig)

        CsmakeServiceConfig.ensure(self)

        if self.manager.options['change-env-vars']:
            os.putenv('KRB5_CONFIG', pathToConfig)
            os.environ['KRB5_CONFIG'] = pathToConfig

    def writefile(self, fobj):
        realm = self.manager.options['realm']
        address, port = self.manager.options['port'].address()
        fobj.write("""[libdefaults]
    default_realm = %s
    rdns = false
    permitted_enctypes = RC4-HMAC

[realms]
    %s = {
        kdc = %s:%d
        default_domain = %s
    }

[domain_realm]
    %s = %s
""" % (realm.upper(), realm.upper(), address, port, realm.lower(),
       realm.lower(), realm.upper()) )

class KdcDaemonConfig(CsmakeServiceConfig):
    CONFIG_FILE_NAME = "csmake.kdc.conf"
    DATABASE_FILE_NAME = "csmake.kdc.db"

    def ensure(self):
        pathToConfig = os.path.join(
            self.path,
            self.CONFIG_FILE_NAME )
        self.log.debug("Writing config to: %s", pathToConfig)
        self._backupAndSetup(pathToConfig)

        if self.manager.options['change-env-vars']:
            os.putenv('KRB5_KDC_PROFILE', pathToConfig)
            os.environ['KRB5_KDC_PROFILE'] = pathToConfig
            if self.module.settings['debug'] or self.module.settings['dev-output'] and not self.module.settings['quiet']:
                tracepath = '/dev/stdout'
                if self.module.settings['log'] is not None:
                    tracepath = self.module.settings['log']
                os.putenv('KRB5_TRACE', tracepath)
                os.environ['KRB5_TRACE'] = tracepath

        CsmakeServiceConfig.ensure(self)


    def writefile(self, fobj):
        #For now, we're only going to support RC4-HMAC because it's fast and
        #it's all that seems to work in windows.

        fullkdb5util = self.manager.shellout(
            subprocess.check_output,
            ['which', 'kdb5_util'] ).strip()

        pathToDb = os.path.join(
            self.path,
            self.DATABASE_FILE_NAME )

        pathToStash = os.path.join(
            self.path,
            self.DATABASE_FILE_NAME + ".stash" )

        pathToConfig = os.path.join(
            self.path,
            self.CONFIG_FILE_NAME )

        self.manager.shellout(
            subprocess.check_call,
            [ fullkdb5util, "-sf", pathToStash, "-d", pathToDb,
                   "-k", "RC4-HMAC", "-P", "csmake",
                   "-r", self.manager.options['realm'],
                   "create", "-s" ] )

        filetext = """[realms]
    %s = {
        database_name = %s
        key_stash_file = %s
        supported_enctypes = RC4-HMAC
    }
[logging]
    kdc=CONSOLE""" % (self.manager.options['realm'], pathToDb, pathToDb + '.stash' )
        fobj.write(filetext)
        
    def clean(self):
        pathToDb = os.path.join(
            self.path,
            self.DATABASE_FILE_NAME )

        pathToStash = os.path.join(
            self.path,
            self.DATABASE_FILE_NAME + ".stash" )

        pathToConfig = os.path.join(
            self.path,
            self.CONFIG_FILE_NAME )

        self.manager.shellout(
            subprocess.call,
            ['rm', '-f', pathToConfig, pathToDb, '%s.ok' % pathToDb,
                         '%s.kadm5' % pathToDb, '%s.stash' % pathToDb,
                         '%s.kadm5.lock' % pathToDb ] )
        
        
class KdcServiceConfigManager(CsmakeServiceConfigManager):

    #TODO: Ensure we keep chrootability
    #      We may want to specify the config location in the section
    def __init__(self, module, daemon, cwd=None, options={}):
        CsmakeServiceConfigManager.__init__(self, module, daemon, cwd, options)
        mybaseroot = '/'
        if self.chroot is not None:
            mybaseroot = self.chroot
        self.daemonConfigPath = ''
        if options['config-path'] is not None:
            self.daemonConfigPath = options['config-path'].lstrip('/')
        self.fullDaemonConfigPath = os.path.join(
            mybaseroot,
            self.daemonConfigPath)

    def getKdcDaemonConfigFile(self):
        return os.path.join(
            self.daemonConfigPath,
            KdcDaemonConfig.CONFIG_FILE_NAME )

    def ensure(self):
        try:
            try:
                self.shellout(
                    subprocess.check_output,
                    ['stat', '-c', '', self.fullDaemonConfigPath],
                    in_chroot=False,
                    quiet_check=True )
                result=0
            except:
                result=1
            if result == 0:
                self.log.devdebug("The kdc config directory already exists")
            else:
                self.log.devdebug("The kdc config directory does not exist, creating")
                self.shellout(
                    subprocess.check_call,
                    ['mkdir', '-p', self.fullDaemonConfigPath],
                    in_chroot=False)
        except:
            self.log.exception("Attempt to create kdc config directory '%s' failed", self.fullDaemonConfigPath )
            self.log.warning("The kdc will not have the appropriate configuration")

        CsmakeServiceConfigManager.ensure(self)

    def clean(self):
        CsmakeServiceConfigManager.clean(self)
        if os.path.exists(self.fullDaemonConfigPath):
            try:
                self.shellout(
                    subprocess.check_output,
                    ['rmdir', '-p', self.fullDaemonConfigPath],
                    in_chroot = False,
                    quiet_check=True )
            except Exception as e:
                self.log.devdebug(
                    "The kdc config could not be deleted '%s': %s: %s",
                    self.fullDaemonConfigPath,
                    e.__class__.__name__,
                    str(e) )

class KdcServiceDaemon(CsmakeServiceDaemon):
    def __init__(self, module, provider, options):
        CsmakeServiceDaemon.__init__(self, module, provider, options)
        self.configManagerClass = KdcServiceConfigManager
        self.process = None

    def _setupConfigs(self):
        prefix = ''
        if self.options['config-path'] is not None:
            prefix = [self.options['config-path']]

        #Handle the server side configuration
        self.configManager.register(
            KdcDaemonConfig,
            prefix,
            ensure=False )

        #Handle the client side configuration
        self.configManager.register(
            KdcClientConfig,
            prefix,
            ensure=False )

        CsmakeServiceDaemon._setupConfigs(self)

    def _startListening(self):
        fullkdc = self.configManager.shellout(
            subprocess.check_output,
            ['which', 'krb5kdc'] ).strip()
        #TODO: Figure out command and environment for kdc
        #      Thoughts may include
        #      KRB5_CONFIG (multiple files with colon) for the client
        #      KRB5_KDC_PROFILE for the kdc
        #      KRB5CCNAME possibly for the cached information
        port = self.options['port']
        port.lock()
        command = [
          fullkdc.strip(), '-n', '-p', str(port.address()[1]), '-r', self.options['realm']
        ]
        self.log.debug("Calling Popen with: %s", ' '.join(command))
        port.unbind()
        #time.sleep(360)
        try:
            self.process = self.configManager.shellout(
                subprocess.Popen,
                command,
                with_user_env=True )
            if self.process.poll() is not None:
                raise Exception("Process is not running")
            address = port.address()
            #Wait for 5 seconds to see the process come about
            for x in range(0,50):
                try:
                    subprocess.check_call(
                        ['nc', '-u', '-z', address[0], str(address[1])] )
                    #Process is listening - probably
                    if self.process.poll() is not None:
                        raise Exception("Process is not running")
                    break
                except:
                    #Process is not listening yet wait .1 sec and try again
                    time.sleep(.1)
                    if self.process.poll() is not None:
                        raise Exception("Process is not running")
            else:
                if self.process.poll() is not None:
                    raise Exception("Process never started")
                else:
                    raise Exception("Process didn't listen after 5 seconds")
        finally:
            port.unlock()

    def _cleanup(self):
        try:
            try:
                processes = self.configManager.shellout(
                    subprocess.check_output,
                    [ 'ps', '-o', 'pid', '--ppid', str(self.process.pid), '--noheaders' ] )
                processes = processes.split()
                for process in processes:
                    self.configManager.shellout(
                        subprocess.call,
                        [ 'kill', '-9', process ] )
            except:
                self.log.exception("Could not stop kdc using standard procedure, attempting to use sudo calls exclusively")
                subprocess.call("""set -eux
                    for x in `sudo ps -o pid --ppid %d --noheaders`
                    do
                        sudo kill -9 $x
                    done
                    """ % self.process.pid,
                    shell=True,
                    stdout=self.log.out(),
                    stderr=self.log.err() )
                subprocess.call(
                    ['sudo', 'kill', str(self.process.pid)],
                    stdout=self.log.out(),
                    stderr=self.log.err())
        except:
            self.log.exception("Couldn't terminate process cleanly")

class KdcServiceProvider(CsmakeServiceProvider):

    serviceProviders = {}

    def __init__(self, module, tag, **options):
        CsmakeServiceProvider.__init__(self, module, tag, **options)
        self.serviceClass = KdcServiceDaemon
        self.fullkadminlocal = None

    def _processOptions(self):
        CsmakeServiceProvider._processOptions(self)
        if 'config-path' not in self.options:
            self.options['config-path'] = tempfile.mkdtemp(prefix='csmake-kerberos-')
        if 'realm' not in self.options:
            self.options['realm'] = 'CSMAKE.DOMAIN'

        if 'change-env-vars' not in self.options:
            self.options['change-env-vars'] = True
        else:
            self.options['change-env-vars'] = self.options['change-env-vars'] == 'True'

        if 'config-dir-env' in self.options:
            self.module.env.env[self.options['config-dir-env']] = self.options['config-path']

        if 'principals' not in self.options or self.options['principals'] is None:
            self.options['principals'] = []
        else:
            self.options['principals'] = self.module._parseCommaAndNewlineList(self.options['principals'])

    def startService(self):
        self.service = CsmakeServiceProvider.startService(self)

        self.fullkadminlocal = self.service.configManager.shellout(
            subprocess.check_output,
            ['which', 'kadmin.local'] ).strip()
        for principal in self.options['principals']:
            if ':' in principal:
                principal, password = principal.split(':',1)
                self.addPrincipal(principal, password)
            else:
                self.addPrincipal(principal)
        
    def addPrincipal(self, principal, password='csmake'):
        principal = principal.split('@')[0]
        self.service.configManager.shellout(
            subprocess.check_call,
            [self.fullkadminlocal, '-r', self.options['realm'],
               '-p', "K/M", '-q', 'add_principal -pw %s -e RC4-HMAC %s' % (
                                   password, principal ) ],
            with_user_env=True )

    def deletePrincipal(self, principal):
        principal = principal.split('@')[0]
        self.service.configManager.shellout(
            subprocess.check_call,
            [self.fullkadminlocal, '-r', self.options['realm'],
                '-p', 'K/M', '-q', 'delete_principal --force %s' % principal],
            with_user_env=True )
