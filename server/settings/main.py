from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)

class NetworkSettings(BaseSettingsModel):
    conn_name: str = SettingsField(
        title="Connection Name",
        default_factory=str,
    )
    conn_port: int = SettingsField(
        title="Connection Port",
        default_factory=int,
    )
    timeout: int = SettingsField(
        title="Timeout in Seconds",
        default_factory=int,
    )

class Submitter(BaseSettingsModel):
    enabled: bool = SettingsField(True)
    network: NetworkSettings = SettingsField(
        title="Network Settings",
        default_factory=NetworkSettings,
    )
