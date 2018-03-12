import os
import os.path as osp

from .helper import BuildArtifactsHelper
from .assessment_summary import AssessmentSummary
from .swa_tool import SwaTool

from .. import gencmd
from .. import utillib


class RoslynSecurityGuard(SwaTool):

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

        if 'analyzer-files' in self._tool_conf:
            analyzer_files = [_file for _file in self._tool_conf['analyzer-files'].split('\n')
                              if osp.isfile(_file)]

            if not analyzer_files:
                raise Exception

            self._tool_conf['analyzer'] = ['/analyzer:' + _file for _file in analyzer_files]
        
    def _get_build_artifacts(self, build_artifacts_helper, results_root_dir):

        for artifacts in build_artifacts_helper.get_build_artifacts(self.get_tool_target_artifacts()):
            if 'classpath' in artifacts:
                artifacts['classpath'] = ['/reference:' + _file for _file in artifacts['classpath']]

            if 'flag' in artifacts and '/warnaserror+' in artifacts['flag']:
                artifacts['flag'].remove('/warnaserror+')
                
            artifacts['build-artifact-id'] = artifacts['id']
            artifacts['results-root-dir'] = results_root_dir

            if 'project-file' in artifacts and osp.isfile(artifacts['project-file']):
                artifacts['assessment-working-dir'] = osp.dirname(artifacts['project-file'])
            
            artifacts.update(self._tool_conf)
            artifacts['assessment-report'] = osp.join(artifacts['results-root-dir'],
                                                      artifacts['assessment-report-template'].format(artifacts['build-artifact-id']))

            for new_artifacts in self._split_build_artifacts(artifacts):
                yield new_artifacts


class DevskimTool(SwaTool):

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

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

        return (passed, failed, None, assessment_summary_file)
