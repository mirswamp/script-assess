
import subprocess
import os.path as osp
import re
import xml.etree.ElementTree as ET
import sys


def get_cmd_output(cmd, cwd=None):
    try:
        output = subprocess.check_output(cmd, cwd=cwd)
        return output.decode('utf-8').strip()
    except subprocess.CalledProcessError:
        return None


def get_module_files(sln_file, pkg_build_dir):

    if not osp.isfile(osp.join(pkg_build_dir, sln_file)):
        raise FileNotFoundError(osp.join(pkg_build_dir, sln_file))

    cmd = ['dotnet', 'sln', sln_file, 'list']

    proj_regex = re.compile(r'.+[.](csproj|vbproj)$')
    for line in get_cmd_output(cmd, pkg_build_dir).split('\n'):
        if proj_regex.match(line) != None:
            yield line


def get_target_framworks(proj_file):

    if not osp.isfile(proj_file):
        raise FileNotFoundError(proj_file)

    root = ET.parse(proj_file).getroot()

    if root.tag != 'Project':
        raise NameError('Not a C# Project file')

    for property_group in root.iter('PropertyGroup'):
        for elem in property_group:
            if elem.tag == 'TargetFramework':
                return [elem.text]
            elif elem.tag == 'TargetFrameworks':
                return elem.text.split(';')


if __name__ == '__main__':

    for proj_file in get_module_files(sys.argv[1], sys.argv[2]):

    #for proj_file in get_module_files('Ocelot.sln',
    #                                  '/Users/vamshi/swamp/dotnet/packages/Ocelot-2.0.4'):

            print('{0}: {1}'.format(proj_file, get_target_framworks(osp.join(sys.argv[2], proj_file))))



