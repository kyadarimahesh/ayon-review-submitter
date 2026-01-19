import os
from collections import defaultdict
from pathlib import Path
from .settings_helper import get_product_filters

try:
    import rv.commands
except ImportError:
    rv = None

try:
    from ayon_openrv.plugins.load.openrv.load_frames import FramesLoader
    from ayon_openrv.plugins.load.openrv.load_mov import MovLoader
except ImportError:
    FramesLoader = None
    MovLoader = None

import ayon_api
from ayon_api import get_task_by_id
from ayon_core.pipeline.load import get_representation_path
from ayon_core.lib.transcoding import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS


class OpenRVStackHandler:
    """Handler for creating AUTO stack in OpenRV"""

    @staticmethod
    def create_auto_stack(contexts):
        """Create AUTO stack in OpenRV for the given context"""
        if rv is None:
            print("RV module not available")
            return False

        ext_groups = defaultdict(list)

        for ctx in contexts:
            OpenRVStackHandler._fetch_and_group_representations(ctx, ext_groups)

        stack_nodes = OpenRVStackHandler._create_stacks_and_layouts(ext_groups)

        if stack_nodes:
            rv.commands.setViewNode(stack_nodes[0])
            rv.commands.setFrame(1)

        return True

    @staticmethod
    def _fetch_and_group_representations(ctx, ext_groups):
        """Fetch representations and auto-compare with last submission"""
        project_name = ctx["project"]["name"]
        version_id = ctx["version"]["id"]
        product_id = ctx["product"]["id"]
        product_name = ctx["product"]["name"]
        product_type = ctx["product"]["productType"]
        version_name = ctx["version"]["name"]
        folder_id = ctx["product"]["folderId"]
        task_id = ctx["version"]["taskId"]

        repres = list(ayon_api.get_representations(project_name, version_ids=[version_id]))

        # Auto-compare with last submission if same product
        product_filters = get_product_filters()
        auto_compare_types = product_filters.get("auto_compare_product_types", ["render", "prerender", "plate"])

        if task_id and product_type in auto_compare_types:
            try:
                task = get_task_by_id(project_name, task_id)
                loaded_products = task.get("data", {}).get("submission_data", {}).get("loaded_products", {})

                if product_id in loaded_products:
                    last_version_id = loaded_products[product_id]["version_id"]

                    if last_version_id != version_id:
                        prev_repres = list(ayon_api.get_representations(project_name, version_ids=[last_version_id]))
                        repres.extend(prev_repres)
                        print(
                            f"Comparing {product_name} {version_name} with {loaded_products[product_id]['version_name']}")
            except Exception as e:
                print(f"Could not fetch last submission: {e}")

        versions = list(ayon_api.get_versions(project_name, product_ids=[product_id]))
        version_map = {v["id"]: v for v in versions}

        for repre in repres:
            # Skip thumbnail representations
            if repre.get("name") == "thumbnail":
                continue

            repre_ctx = ctx.copy()
            repre_ctx["representation"] = repre
            repre_ctx["version"] = version_map.get(repre["versionId"])
            if repre_ctx["version"]:
                OpenRVStackHandler._group_by_extension(repre_ctx, ext_groups)

    @staticmethod
    def _group_by_extension(context, ext_groups):
        """Group representation by extension"""
        filepath = get_representation_path(context["representation"])
        ext = os.path.splitext(filepath)[1].lower()
        ext_groups[ext].append(context)

    @staticmethod
    def _create_stacks_and_layouts(ext_groups):
        """Create stacks and layouts for grouped extensions"""
        stack_nodes = []

        for ext, contexts in ext_groups.items():
            if len(contexts) > 1:
                source_groups, version_names = OpenRVStackHandler._load_sources(contexts)

                if source_groups:
                    product_name = contexts[0]["product"]["name"]
                    version_comparison = "/".join(version_names)
                    stack_node = OpenRVStackHandler._create_stack(ext, source_groups, version_comparison, product_name)
                    OpenRVStackHandler._create_layout(ext, source_groups, version_comparison, product_name)
                    stack_nodes.append(stack_node)
            else:
                OpenRVStackHandler._load_representation(contexts[0])

        return stack_nodes

    @staticmethod
    def _load_sources(contexts):
        """Load sources for stacking using standard loaders"""
        source_groups = []
        version_names = []

        for ctx in contexts:
            try:
                # Use standard loader for consistency
                loaded_node = OpenRVStackHandler._load_representation(ctx)

                if loaded_node:
                    source_group = rv.commands.nodeGroup(loaded_node)
                    source_groups.append(source_group)
                    version_names.append(ctx["version"]["name"])
            except Exception as e:
                print(f"Error loading {ctx.get('version', {}).get('name', 'unknown')}: {e}")

        return source_groups, version_names

    @staticmethod
    def _create_stack(ext, source_groups, version_comparison, product_name):
        """Create RV stack node"""
        stack_node = rv.commands.newNode("RVStackGroup")
        rv.commands.setNodeInputs(stack_node, source_groups)
        rv.commands.setStringProperty(f"{stack_node}.ui.name", [f"{product_name}_{ext}_stack({version_comparison})"])
        return stack_node

    @staticmethod
    def _create_layout(ext, source_groups, version_comparison, product_name):
        """Create RV layout node"""
        layout_node = rv.commands.newNode("RVLayoutGroup")
        rv.commands.setNodeInputs(layout_node, source_groups)
        rv.commands.setStringProperty(f"{layout_node}.layout.mode", ["packed"])
        rv.commands.setStringProperty(f"{layout_node}.ui.name", [f"{product_name}_{ext}_layout({version_comparison})"])
        return layout_node

    @staticmethod
    def _load_representation(context):
        """Load single representation using standard loaders"""
        filepath = get_representation_path(context["representation"])
        ext = Path(filepath).suffix.lower().lstrip('.')

        # Choose appropriate loader based on file extension
        if ext in {e.lstrip('.') for e in VIDEO_EXTENSIONS} and MovLoader:
            loader = MovLoader()
        elif ext in {e.lstrip('.') for e in IMAGE_EXTENSIONS} and FramesLoader:
            loader = FramesLoader()

        # Use loader to load representation
        namespace = context.get("folder", {}).get("name", "default")
        loader.load(context, name=os.path.basename(filepath), namespace=namespace, options=None)

        # Return the loaded source node
        sources = rv.commands.sourcesAtFrame(rv.commands.frame())
        return sources[-1] if sources else None

    @staticmethod
    def get_loaded_products_data(project_name):
        """Get loaded products data for submission_data storage"""
        if rv is None:
            return {}

        loaded_products = {}
        sources = rv.commands.nodesOfType("RVSource")

        for source in sources:
            try:
                if not rv.commands.propertyExists(f"{source}.ayon.version_id"):
                    continue

                version_id = rv.commands.getStringProperty(f"{source}.ayon.version_id")[0]
                version = ayon_api.get_version_by_id(project_name, version_id)

                if version:
                    product_id = version["productId"]
                    product = ayon_api.get_product_by_id(project_name, product_id)

                    loaded_products[product_id] = {
                        "version_id": version_id,
                        "version_name": version["name"],
                        "product_name": product["name"],
                        "product_type": product["productType"]
                    }
            except Exception as e:
                print(f"Error reading product data: {e}")

        return loaded_products
