import os

from ayon_core.addon import AYONAddon, IHostAddon, IPluginPaths
from ayon_core.settings import get_project_settings

from .version import __version__

from .constants import REVIEW_SUBMITTER_ROOT_DIR


class ReviewSubmitterAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "review_submitter"
    host_name = "reviewsubmitter"
    version = __version__

    def get_plugin_paths(self):
        return {}

    def get_load_plugin_paths(self, host_name):
        """Return loader plugin paths only for OpenRV host."""
        if host_name != "openrv":
            return []
        loader_dir = os.path.join(REVIEW_SUBMITTER_ROOT_DIR, "plugins", "submitter")
        return [loader_dir]

    def get_project_settings(self, project_name):
        """Get addon settings for project."""
        settings = get_project_settings(project_name)
        return settings.get(self.name, {})
