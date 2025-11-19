from typing import Type
from ayon_server.addons import BaseServerAddon
from .settings import Submitter

class SubmiterAddon(BaseServerAddon):
    settings_model: Type[Submitter] = Submitter
