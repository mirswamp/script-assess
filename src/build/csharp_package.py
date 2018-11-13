import os
import os.path as osp
import xml.etree.ElementTree as ET

from .package import Package
from ..logger import LogTaskStatus
from .build_summary import BuildSummary
from . import common

from .. import fileutil

from .. import utillib

import pdb
import json
from collections import namedtuple

BuildInfo = namedtuple('BuildInfo', ['build_cmd', 'build_dir', 'build_id'])


class CsharpPkg(Package):

    BUILD_SUBCMD = 'build'
    BUILD_VERBOSITY = '/verbosity:normal'
    BUILD_MONITOR = osp.join(os.getenv('SCRIPTS_DIR'),
                             'dotnet', 'SwampBuildMonitor', 'bin',
                             'Debug', 'netstandard2.0', 'SwampBuildMonitor.dll')

    SLN_FILES_TAG = 'sln_files'
    PROJ_FILES_TAG = 'proj_files'
            
    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)
        self.build_monitor_outfiles = list()

    @classmethod
    def dotnet_executable(cls):
        if utillib.platform() == 'Windows_NT':
            return 'dotnet.exe'
        else:
            return 'dotnet'

    @classmethod
    def get_build_command(cls, build_file,
                          build_monitor_outfile,
                          target_framework=None,
                          build_config=None):

        cmd = [cls.dotnet_executable(),
               CsharpPkg.BUILD_SUBCMD,
               CsharpPkg.BUILD_VERBOSITY,
               '/logger:XmlLogger,{0};{1}'.format(CsharpPkg.BUILD_MONITOR,
                                                  build_monitor_outfile)]

        if target_framework:
            #cmd.append('/property:TargetFramework={0}'.format(target_framework))
            cmd.append('--framework')
            cmd.append(target_framework)

        if build_config:
            cmd.append('--configuration')
            cmd.append(build_config)

        if build_file:
            cmd.append(build_file)

        return cmd

    def get_build_cmds(self, build_root_dir, pkg_build_dir):

        if 'package-build-settings' in self.pkg_conf and \
           self.pkg_conf['package-build-settings'] is not None:

            build_settings = json.loads(self.pkg_conf['package-build-settings'])

            if CsharpPkg.SLN_FILES_TAG in build_settings and \
               build_settings[CsharpPkg.SLN_FILES_TAG]:

                # There is only one sln_file always
                sln_file = list(build_settings[CsharpPkg.SLN_FILES_TAG].keys())[0]

                # if no proj files listed
                if len(build_settings[CsharpPkg.SLN_FILES_TAG][sln_file]) == 0:
                    build_id = 1
                    bm_outfile = osp.join(build_root_dir,
                                          'build_artifacts-{0}.xml'.format(build_id))
                    self.build_monitor_outfiles.append(bm_outfile)

                    build_cmd = CsharpPkg.get_build_command(proj, bm_outfile)
                    yield BuildInfo(build_cmd, pkg_build_dir, build_id)
                else:
                    # When there are one or more proj files 
                    dotnet_projects = build_settings[CsharpPkg.PROJ_FILES_TAG]

                    build_id = 1
                    for proj in build_settings[CsharpPkg.SLN_FILES_TAG][sln_file]:
                        if dotnet_projects[proj].get('nobuild', 'false') == 'false':
                            bm_outfile = osp.join(build_root_dir,
                                                  'build_artifacts-{0}.xml'.format(build_id))
                            self.build_monitor_outfiles.append(bm_outfile)

                            build_cmd = CsharpPkg.get_build_command(proj,
                                                                    bm_outfile,
                                                                    dotnet_projects[proj].get('framework'),
                                                                    dotnet_projects[proj].get('configuration'))

                            yield BuildInfo(build_cmd,
                                            osp.join(pkg_build_dir, osp.dirname(sln_file)),
                                            build_id)
                            build_id = build_id + 1
                
            else:
                # When there are no sln files, but projects
                dotnet_projects = build_settings[CsharpPkg.PROJ_FILES_TAG]

                build_id = 1
                for proj in dotnet_projects.keys():
                    if dotnet_projects[proj].get('nobuild', 'false') == 'false':
                        bm_outfile = osp.join(build_root_dir,
                                              'build_artifacts-{0}.xml'.format(build_id))
                        self.build_monitor_outfiles.append(bm_outfile)

                        build_cmd = CsharpPkg.get_build_command(proj,
                                                                bm_outfile,
                                                                dotnet_projects[proj].get('framework'),
                                                                dotnet_projects[proj].get('configuration'))
                        
                        yield BuildInfo(build_cmd, pkg_build_dir, build_id)
                        build_id = build_id + 1

        else:
            build_id = 1
            bm_outfile = osp.join(build_root_dir,
                                  'build_artifacts-{0}.xml'.format(build_id))
            self.build_monitor_outfiles.append(bm_outfile)

            build_cmd = CsharpPkg.get_build_command(self.pkg_conf.get('build-file'),
                                                    bm_outfile,
                                                    self.pkg_conf.get('package-target-framework'),
                                                    None)
            yield BuildInfo(build_cmd, pkg_build_dir, build_id)

    def add_build_artifacts(self, build_summary, build_root_dir, pkg_build_dir):

        build_artifacts = ET.Element('build-artifacts')
        compiled_projects = set()

        for bm_outfile in self.build_monitor_outfiles:
            if osp.isfile(bm_outfile):

                for dc_elem in ET.parse(bm_outfile).getroot().findall('dotnet-compile'):
                    proj_file = dc_elem.find('project-file')

                    if proj_file is not None and proj_file.text not in compiled_projects:
                        build_artifacts.append(dc_elem)
                        compiled_projects.add(proj_file.text)
                    
        build_summary.add_to_root(build_artifacts)

    def _build(self, build_root_dir, build_summary):

        with LogTaskStatus('build'):

            pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                  self.pkg_conf.get('build-dir', '.')))

            if not osp.isdir(pkg_build_dir):
                LogTaskStatus.log_task('chdir-build-dir', 1, None,
                                       "Directory '{0}' not found".format(osp.relpath(pkg_build_dir,
                                                                                      self.pkg_dir)))
                raise NotADirectoryException()

            for build_info in self.get_build_cmds(build_root_dir, pkg_build_dir):
                outfile = osp.join(build_root_dir, 'build-{0}.out'.format(build_info.build_id))
                errfile = osp.join(build_root_dir, 'build-{0}.err'.format(build_info.build_id))

                exit_code, environ = utillib.run_cmd(build_info.build_cmd,
                                                     cwd=build_info.build_dir,
                                                     outfile=outfile,
                                                     errfile=errfile,
                                                     env=self._get_env(build_info.build_dir),
                                                     description='BUILD')

                build_summary.add_command('build', build_info.build_cmd[0],
                                          build_info.build_cmd[1:], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                build_summary.add_exit_code(exit_code)

                if exit_code != 0:
                    raise common.CommandFailedError(build_info.build_cmd,
                                                    exit_code,
                                                    BuildSummary.FILENAME,
                                                    osp.relpath(outfile, build_root_dir),
                                                    osp.relpath(errfile, build_root_dir))

            self.add_build_artifacts(build_summary, build_root_dir, pkg_build_dir)
                
            return (exit_code, BuildSummary.FILENAME)
