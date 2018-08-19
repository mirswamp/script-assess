import os.path as osp
import xml.etree.ElementTree as ET

from ..build.common import LANG_EXT_MAPPING
from ..build.build_summary import BuildSummary


class BuildArtifactsError(Exception):

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class BuildSummaryError(Exception):

    def __init__(self, field, filename):
        Exception.__init__(self)
        self.value = "No `{0}` tag found in `{1}` file".format(field, filename)

    def __str__(self):
        return repr(self.value)


class BuildArtifactsHelper:

    @classmethod
    def _get_file_list(cls, build_root_dir, xml_elem):
        fileset = set()

        for _file in xml_elem:
            if not osp.isabs(_file.text):
                fileset.add(osp.join(build_root_dir, _file.text))
            else:
                fileset.add(_file.text)

        return list(fileset)

    @classmethod
    def get_artifacts(cls, _id, build_summary, artifacts_xml_elem):
        artifacts = dict(build_summary)

        artifacts['id'] = _id
        #artifacts['srcfile'] = list()

        lang_src = {'{0}-src'.format(lang) for lang in LANG_EXT_MAPPING.keys()}
        
        for elem in artifacts_xml_elem:

            if elem.tag in lang_src:
                fileset = BuildArtifactsHelper._get_file_list(artifacts['build-root-dir'], elem)
                artifacts[elem.tag] = fileset
                #artifacts['srcfile'].extend(fileset)

        return artifacts

    @classmethod
    def get_dotnet_artifacts(cls, _id, build_summary, artifacts_xml_elem):
        artifacts = dict(build_summary)

        artifacts['id'] = _id
        artifacts['project-file'] = artifacts_xml_elem.find('project-file').text
        artifacts['executable'] = artifacts_xml_elem.find('executable').text

        flags = artifacts_xml_elem.find('flags')
        if flags:
            artifacts['flag'] = [flag.text for flag in flags.iter('flag')]

        classpath = artifacts_xml_elem.find('classpath')
        if classpath:
            artifacts['classpath'] = [_file.text for _file in classpath.iter('file')]

        srcfile = artifacts_xml_elem.find('srcfile')
        if srcfile:
            artifacts['dotnet-src'] = [_file.text for _file in srcfile.iter('file')]

            #artifacts['srcfile'] = artifacts['dotnet-src']

        library = artifacts_xml_elem.find('library')
        if library:
            artifacts['library'] = [_file.text for _file in library.iter('file')]

        return artifacts
    
    @classmethod
    def _get_build_summary(cls, root):
        '''returns a dictionary'''
        return {elem.tag: elem.text for elem in root
                if(elem.tag not in ['package-conf',
                                    'command',
                                    'build-artifacts',
                                    'build-command'])}

    def __init__(self, build_summary_file):

        root = ET.parse(build_summary_file).getroot()

        if root.tag != 'build-summary':
            raise BuildSummaryError('build-summary', build_summary_file)

        if root.find('exit-code') is None:
            raise BuildSummaryError('exit-code', build_summary_file)
        elif int(root.find('exit-code').text) != 0:
            raise BuildArtifactsError('exit-code not 0 in ' + build_summary_file)

        if root.find('build-root-dir') is None:
            raise BuildSummaryError('build-root-dir', build_summary_file)

        if root.find('build-artifacts') is None:
            raise BuildArtifactsError("No  Source Files or Class Files to Assess! "
                                      "Looks like no files with 'rb' extension were found.")

        self._build_summary = BuildArtifactsHelper._get_build_summary(root)
        self._build_artifacts = root.find('build-artifacts')
        self._package_conf = {elem.tag: elem.text for elem in root.find('package-conf')}

    def __contains__(self, key):
        return True if key in self._build_summary or key in self._package_conf else False

    def __getitem__(self, key):
        return self._build_summary.get(key, self._package_conf.get(key, None))

    def get_pkg_dir(self):
        return osp.normpath(osp.join(osp.join(self._build_summary['build-root-dir'],
                                              self._build_summary['package-root-dir']),
                                     self._package_conf.get('package-dir', '.')))

    def get_pkg_conf(self):
        return self._package_conf
        
    def get_build_artifacts(self, *args):
        ''' this is a generator function
        parses through the xml elements in the tree and
        yeilds objects artifacts that we are interested in provided as a parameter'''

        count = 1

        for elem in self._build_artifacts:

            artifacts = None

            if elem.tag == BuildSummary.PKG_SRC_TAG:
            #if (elem.tag == BuildSummary.PKG_SRC_TAG) and (elem.tag in args):
                artifacts = BuildArtifactsHelper.get_artifacts(count,
                                                               self._build_summary,
                                                               elem)
            elif elem.tag == 'dotnet-compile':
            #elif (elem.tag == 'dotnet-compile') and (elem.tag in args):
                artifacts = BuildArtifactsHelper.get_dotnet_artifacts(count,
                                                                      self._build_summary,
                                                                      elem)

            # This is for tools like cloc/lizard that work on multiple source file formats
            if artifacts:
                lang_src = {'{0}-src'.format(lang) for lang in LANG_EXT_MAPPING.keys()}
                all_src_files = list()
                for file_type in artifacts.keys():
                    if file_type in lang_src:
                        all_src_files.extend(artifacts[file_type])

                artifacts['srcfile'] = all_src_files
                yield artifacts

            count += 1
