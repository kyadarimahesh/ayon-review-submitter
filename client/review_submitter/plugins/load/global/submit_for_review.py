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
        """Load the selected context(s) for review.
        
        Args:
            context: Single context dict or list of context dicts
            name: Optional name override
            namespace: Optional namespace override
            options: Optional loader options
            
        Returns:
            bool: True if successful, False otherwise
        """
        from ayon_core.pipeline import registered_host

        try:
            host = registered_host()
            tool_name = getattr(host, 'name', 'unknown')

            if isinstance(context, list):
                print(f"Processing {len(context)} selected items for review")
            else:
                print("Processing 1 item for review")

            if tool_name == "openrv":
                print("Using OpenRV stack handler")
                return OpenRVStackHandler.create_auto_stack(context)
            else:
                print(f"Using standard review handler for {tool_name}")
                # return ReviewSubmissionHandler.submit_for_review(context)

        except Exception as e:
            print(f"Error during review submission: {e}")
            import traceback
            traceback.print_exc()
            return False
