import os.path as osp

from .helper import BuildArtifactsHelper
from .swa_tool import SwaTool
from ..build.package_python import PythonPkg


class PythonTool(SwaTool):

    def __init__(self, input_root_dir, build_summary_file, tool_root_dir):
        self.set_venv_dir(build_summary_file)
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

    def set_venv_dir(self, build_summary_file):
        build_artifact_helper = BuildArtifactsHelper(build_summary_file)
        build_root_dir = build_artifact_helper['build-root-dir']
        self.venv_dir = osp.join(build_root_dir, PythonPkg.VENV_SUB_DIR)
        
    def _get_env(self):
        new_env = super()._get_env()
        new_env['PATH'] = '%s:%s' % (self.venv_dir, new_env['PATH'])
        return new_env


