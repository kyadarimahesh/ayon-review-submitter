import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from qtpy import QtWidgets, QtCore
from ayon_api import get_server_api_connection, get_tasks, get_folder_by_path, RequestTypes, get_task_by_id, update_task
from ayon_api.operations import OperationsSession
from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline import get_current_context
from ayon_core.tools.utils import host_tools
from .settings_helper import get_product_filters, get_task_settings, get_submission_settings

try:
    import rv.commands as rv
except ImportError:
    rv = None


class ReviewSubmissionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Submit Review")
        self.setFixedSize(400, 350)
        self.reviewer = None
        self.is_high_priority = False
        self.comment = ""
        self.submission_type = None
        self._setup_ui()

    @staticmethod
    def _graphql_query(query: str, variables: dict = None) -> dict:
        try:
            url = os.environ.get("AYON_SERVER_URL", "").rstrip("/") + "/graphql"
            api_key = os.environ.get("AYON_API_KEY", "")

            if not url or not api_key:
                raise Exception("Missing AYON_SERVER_URL or AYON_API_KEY environment variables")

            import requests
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            response = requests.post(
                url,
                json={"query": query, "variables": variables or {}},
                headers=headers,

                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            raise Exception(f"GraphQL query failed: {e}")

    def _fetch_users(self):
        """Fetch AYON users."""
        try:
            query = "query { users { edges { node { name } } } }"
            response = self._graphql_query(query)
            return [edge["node"]["name"] for edge in response.get("data", {}).get("users", {}).get("edges", [])]
        except:
            return ["Users not fetching"]

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        reviewer_label = QtWidgets.QLabel("Select Reviewer:")
        self.reviewer_combo = QtWidgets.QComboBox()
        self.reviewer_combo.addItems(self._fetch_users())

        submission_type_label = QtWidgets.QLabel("Submission Type:")
        self.submission_type_combo = QtWidgets.QComboBox()
        submission_settings = get_submission_settings()
        submission_types = submission_settings.get("submission_types", ["WIP", "FINAL", "PACKAGE"])
        
        print(f"[DIALOG] Submission settings: {submission_settings}")
        print(f"[DIALOG] Submission types to add: {submission_types}")
        
        self.submission_type_combo.addItems(submission_types)

        self.priority_checkbox = QtWidgets.QCheckBox("High Priority")

        comment_label = QtWidgets.QLabel("Comment:")
        self.comment_edit = QtWidgets.QTextEdit()
        self.comment_edit.setMaximumHeight(100)

        self.submit_button = QtWidgets.QPushButton("Submit Review to AYON")
        self.submit_button.clicked.connect(self._on_submit)

        layout.addWidget(reviewer_label)
        layout.addWidget(self.reviewer_combo)
        layout.addWidget(submission_type_label)
        layout.addWidget(self.submission_type_combo)
        layout.addWidget(self.priority_checkbox)
        layout.addWidget(comment_label)
        layout.addWidget(self.comment_edit)
        layout.addStretch()
        layout.addWidget(self.submit_button)

    def _on_submit(self):
        self.reviewer = self.reviewer_combo.currentText()
        self.submission_type = self.submission_type_combo.currentText()
        self.is_high_priority = self.priority_checkbox.isChecked()
        self.comment = self.comment_edit.toPlainText()
        self.accept()

    def get_review_data(self):
        return {
            "reviewer": self.reviewer,
            "submission_type": self.submission_type,
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
                    QtCore.QTimer.singleShot(3000, lambda: ReviewSubmissionHandler._show_review_dialog(parent,
                                                                                                       publisher_window))
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
    def _extract_first_frame_from_rv():
        """Extract the first frame from current RV session as PNG."""
        if not rv:
            return None

        temp_dir = Path(tempfile.gettempdir())
        temp_path = temp_dir / "rv_thumbnail.png"

        try:
            current_frame = rv.frame()
            try:
                rv.setFrame(rv.frameStart())
                rv.exportCurrentFrame(str(temp_path))
            finally:
                rv.setFrame(current_frame)

            return str(temp_path) if temp_path.exists() else None
        except Exception as e:
            print(f"Failed to extract frame from RV: {e}")
            return None

    @staticmethod
    def _upload_thumbnail_to_version(project_name, version_id, thumbnail_path):
        """Upload thumbnail to AYON server and set it for version"""
        try:
            with open(thumbnail_path, "rb") as stream:
                mime_type = "image/png"
                if thumbnail_path.endswith((".jpg", ".jpeg")):
                    if b"\xff\xd8\xff" == stream.read(3):
                        mime_type = "image/jpeg"
                    stream.seek(0)

            conn = get_server_api_connection()
            response = conn.upload_file(
                f"projects/{project_name}/thumbnails",
                thumbnail_path,
                request_type=RequestTypes.post,
                headers={"Content-Type": mime_type}
            )
            response.raise_for_status()
            thumbnail_id = response.json()["id"]

            op_session = OperationsSession()
            op_session.update_entity(
                project_name,
                "version",
                version_id,
                {"thumbnailId": thumbnail_id}
            )
            op_session.commit()
            return True
        except Exception as e:
            print(f"Failed to upload thumbnail: {e}")
            return False

    @staticmethod
    def _create_version_activity(version_id, review_data):
        """Create activity comment on version with user tagging"""
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

        thumbnail_path = ReviewSubmissionHandler._extract_first_frame_from_rv()
        if thumbnail_path:
            ReviewSubmissionHandler._upload_thumbnail_to_version(
                project_name, version_id, thumbnail_path
            )
            try:
                os.remove(thumbnail_path)
            except:
                pass

        context = get_current_context()
        task_name = context.get("task_name")
        if task_name:
            folder_path = context.get("folder_path")
            folder = get_folder_by_path(project_name, folder_path)
            if folder:
                tasks = list(get_tasks(project_name, folder_ids=[folder["id"]], task_names=[task_name]))
                if tasks:
                    task_id = tasks[0]["id"]
                    
                    # Get loaded products from RV
                    from review_submitter.handlers import OpenRVStackHandler
                    loaded_products = OpenRVStackHandler.get_loaded_products_data(project_name)
                    
                    submission_data = {
                        "submission_type": review_data["submission_type"],
                        "reviewer_name": reviewer,
                        "submitter_name": os.environ.get("USERNAME"),
                        "workfile_version_id": version_id,
                        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "loaded_products": loaded_products
                    }
                    
                    task = get_task_by_id(project_name, task_id)
                    task_data = task.get("data", {})
                    task_data["submission_data"] = submission_data
                    update_task(project_name, task_id, data=task_data)

        QtWidgets.QMessageBox.information(
            None,
            "Review Submitted",
            "Review comment sent successfully!"
        )

    @staticmethod
    def collect_review_inputs(parent, is_resubmission=False):
        """Collect review inputs - plates/renders based on submission type"""
        product_filters = get_product_filters()
        
        if is_resubmission:
            filters = product_filters.get("review_target_product_types", ["render"])
        else:
            first_filters = product_filters.get("first_submission_filters", ["plate"])
            review_filters = product_filters.get("review_target_product_types", ["render"])
            filters = first_filters + review_filters

        def apply_filter():
            loader_tool = host_tools.get_tool_by_name("loader", parent=parent)
            loader_tool._search_bar.set_filter_value("product_types", filters)

            context = get_current_context()
            if context:
                project_name = context["project_name"]
                folder_path = context["folder_path"]

                folder = get_folder_by_path(project_name, folder_path)
                if not folder:
                    print(f"Folder not found: {folder_path}")
                    return

                folder_id = folder["id"]
                task_settings = get_task_settings()
                task_names = task_settings.get("inputs_linked_tasks", ["Ingest"]).copy()
                ayon_task_name = os.environ.get("AYON_TASK_NAME")
                if ayon_task_name:
                    task_names.append(ayon_task_name)

                try:
                    tasks = get_tasks(project_name, folder_ids=[folder_id], task_names=task_names)
                    task_ids = [task["id"] for task in tasks] if tasks else []
                    task_ids.append("--no-task--")


                    def select_tasks():
                        from ayon_core.tools.utils.tasks_widget import ITEM_ID_ROLE

                        tasks_view = loader_tool._tasks_widget._tasks_view
                        tasks_proxy = loader_tool._tasks_widget._tasks_proxy_model
                        selection_model = tasks_view.selectionModel()

                        selection_model.clearSelection()

                        for row in range(tasks_proxy.rowCount()):
                            index = tasks_proxy.index(row, 0)
                            item_id = index.data(ITEM_ID_ROLE)
                            if item_id in task_ids:
                                selection_model.select(index,
                                                       QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)

                    QtCore.QTimer.singleShot(300, select_tasks)
                except Exception as e:
                    print(f"Error getting tasks: {e}")

        host_tools.show_loader(parent=parent, use_context=True)
        QtCore.QTimer.singleShot(100, apply_filter)
