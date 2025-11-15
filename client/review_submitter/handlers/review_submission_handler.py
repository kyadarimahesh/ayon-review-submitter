import os
import re
from qtpy import QtWidgets, QtCore
from ayon_api import get_server_api_connection, get_tasks, get_folder_by_path
from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline import get_current_context
from ayon_core.tools.utils import host_tools


class ReviewSubmissionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Submit Review")
        self.setFixedSize(400, 300)
        self.reviewer = None
        self.is_high_priority = False
        self.comment = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        reviewer_label = QtWidgets.QLabel("Select Reviewer:")
        self.reviewer_combo = QtWidgets.QComboBox()
        self.reviewer_combo.addItems([
            "John Smith", "Sarah Johnson", "Mike Davis", "Lisa Chen", "David Wilson"
        ])

        self.priority_checkbox = QtWidgets.QCheckBox("High Priority")

        comment_label = QtWidgets.QLabel("Comment:")
        self.comment_edit = QtWidgets.QTextEdit()
        self.comment_edit.setMaximumHeight(100)

        self.submit_button = QtWidgets.QPushButton("Submit Review to AYON")
        self.submit_button.clicked.connect(self._on_submit)

        layout.addWidget(reviewer_label)
        layout.addWidget(self.reviewer_combo)
        layout.addWidget(self.priority_checkbox)
        layout.addWidget(comment_label)
        layout.addWidget(self.comment_edit)
        layout.addStretch()
        layout.addWidget(self.submit_button)

    def _on_submit(self):
        self.reviewer = self.reviewer_combo.currentText()
        self.is_high_priority = self.priority_checkbox.isChecked()
        self.comment = self.comment_edit.toPlainText()
        self.accept()

    def get_review_data(self):
        return {
            "reviewer": self.reviewer,
            "is_high_priority": self.is_high_priority,
            "comment": self.comment
        }


class ReviewSubmissionHandler:
    """Handler for automated publish and review submission workflow"""
    
    @staticmethod
    def trigger_publish_and_review(parent):
        """Trigger publish button click programmatically"""
        try:
            publisher_window = None
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if hasattr(widget, 'objectName') and widget.objectName() == "PublishWindow":
                    publisher_window = widget
                    break
            
            if publisher_window and hasattr(publisher_window, '_publish_btn'):
                publish_btn = publisher_window._publish_btn
                if publish_btn and publish_btn.isEnabled():
                    publish_btn.click()
                    QtCore.QTimer.singleShot(3000, lambda: ReviewSubmissionHandler._show_review_dialog(parent, publisher_window))
                else:
                    print("Publish button not enabled or not found")
            else:
                print("Publisher window not found or missing _publish_btn attribute")
        except Exception as e:
            print(f"Failed to trigger publish: {e}")
    
    @staticmethod
    def _show_review_dialog(parent, publisher_window):
        """Show review dialog after publish"""
        if publisher_window:
            publisher_window.close()
        
        dialog = ReviewSubmissionDialog(parent=parent)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            review_data = dialog.get_review_data()
            version_id = ReviewSubmissionHandler._get_published_version_id(publisher_window)
            if version_id:
                ReviewSubmissionHandler._create_version_activity(version_id, review_data)
            else:
                print("No published version found to create review comment")
    
    @staticmethod
    def _get_published_version_id(publisher_window):
        """Extract version ID from publish report"""
        if not publisher_window or not hasattr(publisher_window, '_controller'):
            return None
        
        controller = publisher_window._controller
        report = controller.get_publish_report()
        
        if not report or "plugins_data" not in report:
            return None
        
        for plugin_data in report["plugins_data"]:
            if plugin_data.get("name") == "IntegrateAsset":
                instances_data = plugin_data.get("instances_data", [])
                for instance_data in instances_data:
                    logs = instance_data.get("logs", [])
                    for log in logs:
                        msg = log.get("msg", "")
                        if "'versionId':" in msg:
                            match = re.search(r"'versionId':\s*'([^']+)'", msg)
                            if match:
                                return match.group(1)
        
        return None
    
    @staticmethod
    def _create_version_activity(version_id, review_data):
        """Create activity comment on version with user tagging"""
        from ayon_core.pipeline import get_current_project_name
        
        conn = get_server_api_connection()
        project_name = get_current_project_name()
        reviewer = review_data["reviewer"]
        comment = review_data["comment"]
        
        message = comment
        if review_data["is_high_priority"]:
            message = f"🔥 HIGH PRIORITY: {message}"
        if reviewer:
            message += f" [{reviewer}](user:{reviewer})"
        
        conn.create_activity(
            project_name=project_name,
            entity_type="version",
            entity_id=version_id,
            activity_type="comment",
            body=message
        )
        
        QtWidgets.QMessageBox.information(
            None,
            "Review Submitted",
            "Review comment sent successfully!"
        )
    
    @staticmethod
    def collect_review_inputs(parent, is_resubmission=False):
        """Collect review inputs - plates/renders based on submission type"""
        def apply_filter():
            loader_tool = host_tools.get_tool_by_name("loader", parent=parent)
            loader_tool._search_bar.set_filter_value("product_types", ["plate", "render"])

            context = get_current_context()
            if context:
                project_name = context["project_name"]
                folder_path = context["folder_path"]

                folder = get_folder_by_path(project_name, folder_path)
                if not folder:
                    print(f"Folder not found: {folder_path}")
                    return

                folder_id = folder["id"]
                task_names = ["Ingest"]
                ayon_task_name = os.environ.get("AYON_TASK_NAME")
                if ayon_task_name:
                    task_names.append(ayon_task_name)

                try:
                    tasks = get_tasks(project_name, folder_ids=[folder_id], task_names=task_names)
                    if tasks:
                        task_ids = [task["id"] for task in tasks]
                        loader_tool._controller.set_selected_tasks(task_ids)
                        loader_tool._tasks_widget.refresh()
                    else:
                        print(f"No tasks found with names: {task_names}")
                except Exception as e:
                    print(f"Error getting tasks: {e}")

        host_tools.show_loader(parent=parent, use_context=True)
        QtCore.QTimer.singleShot(100, apply_filter)
