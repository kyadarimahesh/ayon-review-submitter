from ayon_core.pipeline import load
from review_submitter.handlers import OpenRVStackHandler, ReviewSubmissionHandler


class CreateRvReviewStack(load.ProductLoaderPlugin):
    """Initiate the Submit for review the selected versions from Ayon and creates comment.
    This function adds a menu in the loader on selection of supported product types"""

    label = "Create RV Review Stack"
    settings_category = "nuke"
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

    def load(self, contexts, name=None, namespace=None, options=None):
        """Load the selected context(s) for review.
        
        Args:
            contexts: Single context dict or list of context dicts
            name: Optional name override
            namespace: Optional namespace override
            options: Optional loader options
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            return OpenRVStackHandler.create_auto_stack(contexts)
        except Exception as e:
            print(f"Error during review submission: {e}")
            import traceback
            traceback.print_exc()
            return False
