import os
import os.path as osp
import xml.etree.ElementTree as ET

from .package import Package

from .. import fileutil

from .. import utillib


class CsharpPkg(Package):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_build_cmd(self, build_root_dir):
        build_monitor = osp.join(os.getenv('SCRIPTS_DIR'),
                                 'dotnet', 'SwampBuildMonitor', 'bin', 'Debug', 'netstandard2.0', 'SwampBuildMonitor.dll')

        self.build_monitor_outfile = osp.join(build_root_dir, 'build_artifacts.xml')

        executable = 'dotnet'
        if utillib.platform() == 'Windows_NT':
            executable = 'dotnet.exe'
        
        cmd = [executable,
               'build',
               '/verbosity:normal',
               '/logger:XmlLogger,{0};{1}'.format(build_monitor,
                                                  self.build_monitor_outfile)]

        if 'package-target-framework' in self.pkg_conf:
            cmd.append('/property:TargetFramework={}'.format(self.pkg_conf['package-target-framework']))

        if 'build-file' in self.pkg_conf:
            cmd.append(self.pkg_conf['build-file'])
        
        return cmd

    def add_build_artifacts(self, build_summary, build_root_dir, pkg_build_dir):
        if not osp.isfile(self.build_monitor_outfile):
            return

        build_artifacts = ET.parse(self.build_monitor_outfile).getroot()
        #pdb.set_trace()
        build_summary.add_to_root(build_artifacts)
        
