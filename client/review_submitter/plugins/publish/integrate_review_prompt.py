import os
import pyblish.api
from qtpy import QtWidgets


class IntegrateReviewPrompt(pyblish.api.ContextPlugin):
    """Prompt for review submission after successful publish"""

    order = pyblish.api.IntegratorOrder + 10
    label = "Review Submission Prompt"
    hosts = ["openrv"]
    optional = True

    def process(self, context):
        """Show review dialog if user opted for review"""
        if not os.environ.get("AYON_PUBLISH_FOR_REVIEW"):
            return

        if self._has_errors(context):
            self.log.info("Publish had errors, skipping review submission")
            os.environ.pop("AYON_PUBLISH_FOR_REVIEW", None)
            return

        version_id = self._get_version_id(context)
        if not version_id:
            self.log.warning("No version_id found, skipping review submission")
            os.environ.pop("AYON_PUBLISH_FOR_REVIEW", None)
            return

        self._show_review_dialog(version_id)
        os.environ.pop("AYON_PUBLISH_FOR_REVIEW", None)

    def _has_errors(self, context):
        """Check if any instance has errors"""
        for result in context.data.get("results", []):
            if result.get("error"):
                return True
        return False

    def _get_version_id(self, context):
        """Extract version_id from published instance"""
        for instance in context:
            version_entity = instance.data.get("versionEntity")
            if version_entity:
                return version_entity.get("id")
        return None

    def _show_review_dialog(self, version_id):
        """Show review submission dialog"""
        from review_submitter.handlers import (
            ReviewSubmissionDialog,
            ReviewSubmissionHandler
        )

        dialog = ReviewSubmissionDialog()
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            review_data = dialog.get_review_data()
            ReviewSubmissionHandler._create_version_activity(version_id, review_data)
