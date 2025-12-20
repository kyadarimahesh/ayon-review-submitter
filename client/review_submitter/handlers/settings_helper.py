"""Helper to retrieve addon settings."""
import logging

logger = logging.getLogger(__name__)


def get_addon_settings():
    """Get Review Submitter addon settings with fallback to defaults."""
    try:
        from ayon_core.addon import AddonsManager
        from ayon_core.pipeline import get_current_project_name

        manager = AddonsManager()
        addon = manager.get("review_submitter")

        if not addon:
            print("Review Submitter addon not found in AddonsManager")
            return _get_default_settings()

        project_name = get_current_project_name()
        if not project_name:
            print("No current project name found")
            return _get_default_settings()

        # Get project settings
        settings = addon.get_project_settings(project_name)

        return settings

    except Exception as e:
        print(f"[SETTINGS] Failed to retrieve settings: {e}")
        import traceback
        traceback.print_exc()
        return _get_default_settings()


def _get_default_settings():
    """Return default settings as fallback."""
    print("[SETTINGS] Using default fallback settings")
    return {
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


def get_product_filters():
    """Get product type filters from settings."""
    settings = get_addon_settings()
    filters = settings.get("product_filters", {})
    return filters


def get_task_settings():
    """Get task settings."""
    settings = get_addon_settings()
    task_settings = settings.get("task_settings", {})
    return task_settings


def get_submission_settings():
    """Get submission settings."""
    settings = get_addon_settings()
    submission = settings.get("submission", {})
    return submission
