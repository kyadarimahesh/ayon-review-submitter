from ayon_server.settings import BaseSettingsModel, SettingsField


class ProductTypeFilters(BaseSettingsModel):
    first_submission_filters: list[str] = SettingsField(
        default_factory=lambda: ["plate"],
        title="First Submission Product Types"
    )
    review_target_product_types: list[str] = SettingsField(
        default_factory=lambda: ["render"],
        title="Review Target Product Types"
    )
    auto_compare_product_types: list[str] = SettingsField(
        default_factory=lambda: ["render", "prerender", "plate"],
        title="Auto-Compare Product Types"
    )


class TaskSettings(BaseSettingsModel):
    inputs_linked_tasks: list[str] = SettingsField(
        default_factory=lambda: ["Ingest"],
        title="Input Linked Task Names"
    )


class SubmissionSettings(BaseSettingsModel):
    auto_submit_on_publish: bool = SettingsField(
        False,
        title="Auto-submit to Review on Publish"
    )
    default_reviewers: list[str] = SettingsField(
        default_factory=list,
        title="Default Reviewers"
    )
    require_comment: bool = SettingsField(
        True,
        title="Require Comment on Submission"
    )
    submission_types: list[str] = SettingsField(
        default_factory=lambda: ["WIP", "FINAL", "PACKAGE"],
        title="Available Submission Types"
    )


class ReviewSubmitterSettings(BaseSettingsModel):
    enabled: bool = SettingsField(True, title="Enable Review Submitter")
    product_filters: ProductTypeFilters = SettingsField(
        default_factory=ProductTypeFilters,
        title="Product Type Filters"
    )
    task_settings: TaskSettings = SettingsField(
        default_factory=TaskSettings,
        title="Task Settings"
    )
    submission: SubmissionSettings = SettingsField(
        default_factory=SubmissionSettings,
        title="Submission Settings"
    )


DEFAULT_VALUES = {
    "enabled": True,
    "product_filters": {
        "first_submission_filters": ["plate"],
        "review_target_product_types": ["render"],
        "auto_compare_product_types": ["render", "prerender", "plate"]
    },
    "task_settings": {
        "inputs_linked_tasks": ["Ingest"]
    },
    "submission": {
        "auto_submit_on_publish": False,
        "default_reviewers": [],
        "require_comment": True,
        "submission_types": ["WIP", "FINAL", "PACKAGE"]
    }
}
