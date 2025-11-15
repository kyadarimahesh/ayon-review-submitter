import os

from ayon_core.addon import AYONAddon, IHostAddon, IPluginPaths

from .version import __version__

REVIEW_SUBMITTER_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ReviewSubmitterAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "reviewsubmitter"
    host_name = "reviewsubmitter"
    version = __version__

    def get_plugin_paths(self):
        return {}

    def get_create_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(REVIEW_SUBMITTER_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "create")]

    def get_publish_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(REVIEW_SUBMITTER_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "publish")]

    def get_load_plugin_paths(self, host_name):
        loaders_dir = os.path.join(REVIEW_SUBMITTER_ROOT_DIR, "plugins", "load")
        # Always return global plugins for all hosts including browser
        return [os.path.join(loaders_dir, "global")]