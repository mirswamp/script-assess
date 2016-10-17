import os
import os.path as osp
import logging
import fnmatch

from .helper import BuildArtifactsHelper
from .assessment_summary import AssessmentSummary
from .swa_tool import SwaToolBase
from .swa_tool import SwaTool

from .. import gencmd
from .. import utillib


class JsTool(SwaTool):

    FILE_TYPE = 'javascript'

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)


class PhpTool(SwaTool):

    FILE_TYPE = 'php'

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)


class Lizard(SwaTool):

    # FILE_TYPE = 'srcfile'

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

    def _get_build_artifacts(self, build_artifacts_helper, results_root_dir):

        for artifacts in build_artifacts_helper.get_build_artifacts('web-src'):
            artifacts['build-artifact-id'] = artifacts['id']
            artifacts['results-root-dir'] = results_root_dir
            artifacts.update(self._tool_conf)
            artifacts['assessment-report'] = osp.join(artifacts['results-root-dir'],
                                                      artifacts['assessment-report-template'].format(artifacts['build-artifact-id']))

            artifacts[SwaTool.FILE_TYPE] = [_file for _file in artifacts[SwaTool.FILE_TYPE]
                                            if osp.splitext(_file)[1] not in ['.css' '.xml']]
            
            for new_artifacts in self._split_build_artifacts(artifacts):
                yield new_artifacts
        
        
class Flow(SwaToolBase):

    def __init__(self, input_root_dir, tool_root_dir):
        SwaToolBase.__init__(self, input_root_dir, tool_root_dir)

    @classmethod
    def _convert_to_regex(cls, pattern):
        regex = fnmatch.translate(pattern)
        # fnmatch adds this to the end of the regex, don't understand why
        if regex.endswith('\\Z(?ms)'):
            regex = regex.rpartition('\\Z(?ms)')[0]

        return regex

    def _create_flowconfig(self, assessment_working_dir):

        if not osp.isfile(osp.join(assessment_working_dir, '.flowconfig')):

            content = '''[include]\n\n[libs]\n\n[options]\n\n[ignore]\n<PROJECT_ROOT>/node_modules\n'''
            if self.build_artifacts_helper['package-exclude-paths']:
                # TODO: These may have to converted into ocaml regex
                ignore_patterns = '\n'.join({'<PROJECT_ROOT>/' + self._convert_to_regex(pattern.strip()) for pattern in
                                             self.build_artifacts_helper['package-exclude-paths'].split(',')})
                content += ignore_patterns + '\n'

            ignore_file = None
            if osp.isfile(osp.join(assessment_working_dir, '.npmignore')):
                ignore_file = osp.join(assessment_working_dir, '.npmignore')
            elif osp.isfile(osp.join(assessment_working_dir, '.gitignore')):
                ignore_file = osp.join(assessment_working_dir, '.gitignore')

            if ignore_file:
                with open(ignore_file) as fobj:
                    ignore_patterns = {p.strip().strip('\n') for p in fobj
                                       if p and not p.isspace() and not p.strip().startswith('#')}
                    content += '\n'.join({'<PROJECT_ROOT>/' + self._convert_to_regex(pattern)
                                          for pattern in ignore_patterns})
                    content += '\n'

            with open(osp.join(assessment_working_dir, '.flowconfig'), 'w') as fobj:
                logging.info('DOT FLOWCONFIG: %s', content)
                fobj.write(content)

    def assess(self, build_summary_file, results_root_dir):

        if not osp.isdir(results_root_dir):
            os.makedirs(results_root_dir, exist_ok=True)

        assessment_summary_file = osp.join(results_root_dir, 'assessment_summary.xml')

        self.build_artifacts_helper = BuildArtifactsHelper(build_summary_file)

        passed = 0
        failed = 0
        with AssessmentSummary(assessment_summary_file,
                               self.build_artifacts_helper,
                               self._tool_conf) as assessment_summary:

            artifacts = {'id': 1}

            artifacts.update(self._tool_conf)
            assessment_report = osp.join(results_root_dir,
                                         artifacts['assessment-report-template'].format(artifacts['id']))

            if 'report-on-stdout' in artifacts \
               and artifacts['report-on-stdout'] == 'true':
                outfile = assessment_report
            else:
                artifacts['assessment-report'] = assessment_report
                outfile = osp.join(results_root_dir,
                                   'swa_tool_stdout{0}.out'.format(artifacts['id']))

            errfile = osp.join(results_root_dir,
                               'swa_tool_stderr{0}.out'.format(artifacts['id']))

            assess_cmd = gencmd.gencmd(osp.join(self.input_root_dir,
                                                artifacts['tool-invoke']),
                                       artifacts)

            # For Flow package dir is assessment working dir
            assessment_working_dir = self.build_artifacts_helper.get_pkg_dir()

            start_time = utillib.posix_epoch()

            # TODO: create flow config
            self._create_flowconfig(assessment_working_dir)

            exit_code, environ = utillib.run_cmd(assess_cmd,
                                                 outfile=outfile,
                                                 errfile=errfile,
                                                 cwd=assessment_working_dir,
                                                 env=self._get_env(),
                                                 description='ASSESSMENT')

            # write assessment summary file
            # return pass, fail, assessment_summary
            assessment_summary.add_report(artifacts['id'],
                                          assess_cmd,
                                          exit_code,
                                          environ,
                                          assessment_working_dir,
                                          assessment_report,
                                          outfile,
                                          errfile,
                                          start_time,
                                          utillib.posix_epoch())

            if self._validate_exit_code(exit_code):
                passed += 1
            else:
                failed += 1

        return (passed, failed, assessment_summary_file)


class Retire(SwaToolBase):

    def __init__(self, input_root_dir, tool_root_dir):
        SwaToolBase.__init__(self, input_root_dir, tool_root_dir)
        
    def assess(self, build_summary_file, results_root_dir):

        if not osp.isdir(results_root_dir):
            os.makedirs(results_root_dir, exist_ok=True)

        assessment_summary_file = osp.join(results_root_dir, 'assessment_summary.xml')

        self.build_artifacts_helper = BuildArtifactsHelper(build_summary_file)

        passed = 0
        failed = 0
        with AssessmentSummary(assessment_summary_file,
                               self.build_artifacts_helper,
                               self._tool_conf) as assessment_summary:

            artifacts = {'id': 1}

            artifacts.update(self._tool_conf)
            assessment_report = osp.join(results_root_dir,
                                         artifacts['assessment-report-template'].format(artifacts['id']))

            if 'report-on-stdout' in artifacts \
               and artifacts['report-on-stdout'] == 'true':
                outfile = assessment_report
            else:
                artifacts['assessment-report'] = assessment_report
                outfile = osp.join(results_root_dir,
                                   'swa_tool_stdout{0}.out'.format(artifacts['id']))

            errfile = osp.join(results_root_dir,
                               'swa_tool_stderr{0}.out'.format(artifacts['id']))

            assessment_working_dir = self.build_artifacts_helper.get_pkg_dir()
            artifacts['package-dir'] = assessment_working_dir

            if not osp.isfile(osp.join(assessment_working_dir, 'package.json')):
                artifacts['not-node-pkg'] = '--js'
            
            assess_cmd = gencmd.gencmd(osp.join(self.input_root_dir,
                                                artifacts['tool-invoke']),
                                       artifacts)

            start_time = utillib.posix_epoch()

            exit_code, environ = utillib.run_cmd(assess_cmd,
                                                 outfile=outfile,
                                                 errfile=errfile,
                                                 cwd=assessment_working_dir,
                                                 env=self._get_env(),
                                                 description='ASSESSMENT')

            # write assessment summary file
            # return pass, fail, assessment_summary
            assessment_summary.add_report(artifacts['id'],
                                          assess_cmd,
                                          exit_code,
                                          environ,
                                          assessment_working_dir,
                                          assessment_report,
                                          outfile,
                                          errfile,
                                          start_time,
                                          utillib.posix_epoch())

            if self._validate_exit_code(exit_code):
                passed += 1
            else:
                failed += 1

        return (passed, failed, assessment_summary_file)

