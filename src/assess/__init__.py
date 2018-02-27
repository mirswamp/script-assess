import os.path as osp
import shutil
import logging

from .helper import BuildArtifactsError
from .helper import BuildSummaryError
from .swa_tool import SwaToolBase
from .swa_tool import SwaTool
from .web_tools import Flow
from .web_tools import Retire
from .web_tools import PhpTool
from .web_tools import Lizard
from .web_tools import JsTool
from .web_tools import Eslint
from .python_tools import PythonTool
from .csharp_tools import DevskimTool
from .csharp_tools import RoslynSecurityGuard

from .. import utillib
from .. import confreader
from ..logger import LogTaskStatus


def assess(input_root_dir, output_root_dir, tool_root_dir,
           results_root_dir, build_summary_file):

    tool_conf_file = osp.join(input_root_dir, SwaToolBase.TOOL_DOT_CONF)
    tool_conf = confreader.read_conf_into_dict(tool_conf_file)
    tool_type = tool_conf['tool-type'].lower()

    if tool_type == 'flow':
        swa_tool = Flow(input_root_dir, tool_root_dir)
    elif tool_type == 'eslint':
        swa_tool = Eslint(input_root_dir, tool_root_dir)
    elif tool_type == 'retire-js':
        swa_tool = Retire(input_root_dir, tool_root_dir)
    elif tool_type == 'cloc':
        swa_tool = SwaTool(input_root_dir, tool_root_dir)
    elif tool_type == 'lizard':
        swa_tool = Lizard(input_root_dir, tool_root_dir)
    elif tool_type in ['php_codesniffer', 'phpmd']:
        swa_tool = PhpTool(input_root_dir, tool_root_dir)
    elif tool_type in ['pylint', 'bandit', 'flake8', 'radon']:
        swa_tool = PythonTool(input_root_dir, build_summary_file, tool_root_dir)
    elif tool_type == 'devskim':
        swa_tool = DevskimTool(input_root_dir, tool_root_dir)
    elif tool_type in ['roslyn-security-gaurd', 'code-cracker']:
        swa_tool = RoslynSecurityGuard(input_root_dir, tool_root_dir)
    else:
        swa_tool = JsTool(input_root_dir, tool_root_dir)
        
    try:
        with LogTaskStatus('assess') as status_dot_out:

            (passed,
             failed,
             error_msgs,
             assessment_summary_file) = swa_tool.assess(build_summary_file,
                                                        results_root_dir)

            if passed == 0 and failed == 0:
                exit_code = 0
                status_dot_out.skip_task('no files')
                # status_dot_out.skip_task(task_msg=None,
                # task_msg_indetail="No relavent files found to run '%s'" % tool_type)
            else:
                exit_code = 1 if failed else 0
                if failed and error_msgs:
                    LogTaskStatus.log_task('tool-package-compatibility',
                                           exit_code,
                                           'known tool bug',
                                           error_msgs)

                status_dot_out.update_task_status(exit_code,
                                                  'pass: {0}, fail: {1}'.format(passed, failed))
    except (BuildArtifactsError,
            BuildSummaryError) as err:
        logging.exception(err)
        exit_code = 1
        assessment_summary_file = None

    finally:
        results_conf = dict()
        results_conf['exit-code'] = str(exit_code)

        if assessment_summary_file and osp.isfile(assessment_summary_file):
            results_conf['assessment-summary-file'] = osp.basename(assessment_summary_file)

            with LogTaskStatus('results-archive'):
                results_archive = shutil.make_archive(osp.join(output_root_dir, 'results'),
                                                      'gztar',
                                                      osp.dirname(results_root_dir),
                                                      osp.basename(results_root_dir))

                results_conf['results-archive'] = osp.basename(results_archive)
                results_conf['results-dir'] = osp.basename(results_root_dir)

                utillib.write_to_file(osp.join(output_root_dir, 'results.conf'),
                                      results_conf)

    return (exit_code, assessment_summary_file)
