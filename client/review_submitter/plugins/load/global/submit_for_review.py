from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from ayon_core.pipeline import load
from review_submitter.handlers import OpenRVStackHandler, ReviewSubmissionHandler


class SubmitForReview(load.ProductLoaderPlugin):
    """Initiate the Submit for review the selected versions from Ayon and creates comment.
    This function adds a menu in the loader on selection of supported product types"""

    label = "Submit for Review"
    product_types = {"render",
                     "prerender",
                     "plate",
                     "package",
                     "review"}

    representations = {"*"}
    order = -100
    icon = "upload"
    color = "#00FF00"
    is_multiple_contexts_compatible = True

    tool_names = ["library_loader", "loader"]

    def load(self, context, name=None, namespace=None, options=None):
        from ayon_core.pipeline import registered_host
        host = registered_host()
        tool_name = getattr(host, 'name', 'unknown')

        if isinstance(context, list):
            print(f"Processing {len(context)} selected items")

        if tool_name == "openrv":
            return OpenRVStackHandler.create_auto_stack(context)
        else:
            return ReviewSubmissionHandler.submit_for_review(context)
