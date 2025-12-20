import os
import re
from collections import defaultdict
from pathlib import Path
from .settings_helper import get_product_filters

try:
    import rv.commands
except ImportError:
    rv = None

import ayon_api
from ayon_api import get_task_by_id
from ayon_core.pipeline.load import get_representation_path

try:
    from ayon_openrv.api.pipeline import imprint_container
except ImportError:
    imprint_container = None


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
                        print(f"Comparing {product_name} {version_name} with {loaded_products[product_id]['version_name']}")
            except Exception as e:
                print(f"Could not fetch last submission: {e}")

        versions = list(ayon_api.get_versions(project_name, product_ids=[product_id]))
        version_map = {v["id"]: v for v in versions}

        for repre in repres:
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
                    version_comparison = "/".join(version_names)
                    stack_node = OpenRVStackHandler._create_stack(ext, source_groups, version_comparison)
                    OpenRVStackHandler._create_layout(ext, source_groups, version_comparison)
                    stack_nodes.append(stack_node)
            else:
                OpenRVStackHandler._load_representation(contexts[0])

        return stack_nodes

    @staticmethod
    def _load_sources(contexts):
        """Load sources for stacking"""
        source_groups = []
        version_names = []

        for ctx in contexts:
            try:
                filepath = get_representation_path(ctx["representation"])
                load_path = OpenRVStackHandler._prepare_load_path(filepath)
                nodes = rv.commands.addSourcesVerbose([[load_path]])

                if nodes:
                    source_node = nodes[0]
                    source_group = rv.commands.nodeGroup(source_node)
                    source_groups.append(source_group)
                    version_names.append(ctx["version"]["name"])
                    OpenRVStackHandler._store_version_metadata(source_node, ctx)
            except Exception as e:
                print(f"Error loading {ctx.get('version', {}).get('name', 'unknown')}: {e}")

        return source_groups, version_names

    @staticmethod
    def _create_stack(ext, source_groups, version_comparison):
        """Create RV stack node"""
        stack_node = rv.commands.newNode("RVStackGroup")
        rv.commands.setNodeInputs(stack_node, source_groups)
        rv.commands.setStringProperty(f"{stack_node}.ui.name", [f"{ext}_stack({version_comparison})"])
        return stack_node

    @staticmethod
    def _create_layout(ext, source_groups, version_comparison):
        """Create RV layout node"""
        layout_node = rv.commands.newNode("RVLayoutGroup")
        rv.commands.setNodeInputs(layout_node, source_groups)
        rv.commands.setStringProperty(f"{layout_node}.layout.mode", ["packed"])
        rv.commands.setStringProperty(f"{layout_node}.ui.name", [f"{ext}_layout({version_comparison})"])
        return layout_node

    @staticmethod
    def _load_representation(context):
        """Load single representation"""
        filepath = get_representation_path(context["representation"])
        load_path = OpenRVStackHandler._prepare_load_path(filepath)
        loaded_node = rv.commands.addSourceVerbose([load_path])

        OpenRVStackHandler._store_version_metadata(loaded_node, context)

        if imprint_container:
            imprint_container(
                loaded_node,
                name=os.path.basename(filepath),
                namespace=context.get("folder", {}).get("name", "default"),
                context=context,
                loader="OpenRVStackHandler"
            )

        return loaded_node

    @staticmethod
    def read_version_metadata_from_rv():
        """Read version metadata from all sources in current RV session"""
        if rv is None:
            return {}

        source_mapping = {}

        for source in rv.commands.nodesOfType("RVSourceGroup"):
            metadata = OpenRVStackHandler._read_source_metadata(source)
            if metadata:
                source_mapping[source] = metadata

        return source_mapping

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

    @staticmethod
    def _read_source_metadata(source):
        """Read metadata from a single source node"""
        props = {
            'version_id': f"{source}.ayon.version_id",
            'representation_id': f"{source}.ayon.representation_id",
            'path': f"{source}.ayon.file_path"
        }

        if not rv.commands.propertyExists(props['version_id']):
            return None

        return {
            key: rv.commands.getStringProperty(prop)[0] if rv.commands.propertyExists(prop) else None
            for key, prop in props.items()
        }

    @staticmethod
    def _store_version_metadata(node, context):
        """Store version metadata in RV source node"""
        if rv is None:
            return

        metadata = {
            'version_id': context.get("version", {}).get("id"),
            'representation_id': context.get("representation", {}).get("id"),
            'file_path': get_representation_path(context["representation"])
        }

        for key, value in metadata.items():
            if value:
                prop = f"{node}.ayon.{key}"
                if not rv.commands.propertyExists(prop):
                    rv.commands.newProperty(prop, rv.commands.StringType, 1)
                rv.commands.setStringProperty(prop, [value], True)

    @staticmethod
    def _prepare_load_path(path):
        """Prepare path for RV loading (handle image sequences)"""
        ext = Path(path).suffix.lower()

        if ext not in ['.exr', '.jpg', '.jpeg', '.png', '.tiff', '.dpx']:
            return path

        folder = os.path.dirname(path)
        filename = os.path.basename(path)
        match = re.match(r"^(.*?)(\d+)(\.[^.]+)$", filename)

        if not match or not os.path.exists(folder):
            return path

        prefix, _, ext = match.groups()
        pattern = rf"^{re.escape(prefix)}(\d+){re.escape(ext)}$"
        frames = [int(m.group(1)) for f in os.listdir(folder) if (m := re.match(pattern, f))]

        if frames:
            return os.path.join(folder, f"{prefix}{min(frames)}-{max(frames)}#{ext}")

        return path
