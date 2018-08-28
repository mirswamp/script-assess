import re
import os
import os.path as osp
import xml.etree.ElementTree as ET

from .package import Package

from .. import fileutil

from .. import utillib
from ..utillib import FileNotFoundException




class CsharpPkg(Package):

    @classmethod
    def get_project_files(cls, pkg_build_dir, sln_file):
        '''Input is a solutions file, and package build directory'''

        if not osp.isfile(osp.join(pkg_build_dir, sln_file)):
            raise FileNotFoundError(osp.join(pkg_build_dir, sln_file))

        cmd = ['dotnet', 'sln', sln_file, 'list']

        proj_regex = re.compile(r'.+[.](csproj|vbproj)$')
        for line in utillib.get_cmd_output(cmd, pkg_build_dir).split('\n'):
            if proj_regex.match(line) != None:
                yield line

    @classmethod
    def get_target_framworks(cls, proj_file):
        '''proj_file path must be absolute'''

        if not osp.isfile(proj_file):
            raise FileNotFoundError(proj_file)

        root = ET.parse(proj_file).getroot()

        if root.tag != 'Project':
            raise NameError('Not a C# Project file')

        for property_group in root.iter('PropertyGroup'):
            for elem in property_group:
                if elem.tag == 'TargetFramework':
                    return [elem.text.strip()]
                elif elem.tag == 'TargetFrameworks':
                    return [tf.strip() for tf in elem.text.split(';')]


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
        
