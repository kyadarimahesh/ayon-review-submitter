import os
from collections import defaultdict
import ayon_api
import rv
from ayon_core.pipeline.load import get_representation_path
from ayon_openrv.api.pipeline import imprint_container


class OpenRVStackHandler:
    """Handler for creating AUTO stack in OpenRV"""
    
    @staticmethod
    def create_auto_stack(context):
        """Create AUTO stack in OpenRV for the given context"""
        contexts = context if isinstance(context, list) else [context]
        
        # Group representations by extension
        ext_groups = defaultdict(list)
        
        for ctx in contexts:
            if "representation" in ctx:
                OpenRVStackHandler._group_by_extension(ctx, ext_groups)
            else:
                # Fetch representations from version
                project_name = ctx["project"]["name"]
                version_id = ctx["version"]["id"]
                product_type = ctx["product"]["productType"]
                
                repres = list(ayon_api.get_representations(project_name, version_ids=[version_id]))
                
                # Get versions for this product
                product_id = ctx["product"]["id"]
                versions = list(ayon_api.get_versions(project_name, product_ids=[product_id]))
                versions.sort(key=lambda v: v["version"], reverse=True)
                
                # For render products, also get previous version for comparison
                if product_type == "render" and len(versions) > 1:
                    prev_version_id = versions[1]["id"]
                    prev_repres = list(ayon_api.get_representations(project_name, version_ids=[prev_version_id]))
                    repres.extend(prev_repres)
                
                for repre in repres:
                    repre_context = ctx.copy()
                    repre_context["representation"] = repre
                    # Find version info for this representation
                    for version in versions:
                        if version["id"] == repre["versionId"]:
                            repre_context["version"] = version
                            break
                    OpenRVStackHandler._group_by_extension(repre_context, ext_groups)
        
        # Create stacks and layouts for extensions with multiple sources
        stack_nodes = []
        for ext, contexts in ext_groups.items():
            if len(contexts) > 1:
                # Load all representations for this extension
                source_groups = []
                version_names = []
                for ctx in contexts:
                    filepath = get_representation_path(ctx["representation"])
                    load_path = OpenRVStackHandler._prepare_load_path(filepath)
                    
                    # Load using addSourcesVerbose for proper group handling
                    nodes = rv.commands.addSourcesVerbose([[load_path]])
                    if nodes:
                        source_group = rv.commands.nodeGroup(nodes[0])
                        source_groups.append(source_group)
                        version_names.append(ctx["version"]["name"])
                
                # Create version comparison name
                version_comparison = "/".join(version_names)
                
                # Create stack
                stack_node = rv.commands.newNode("RVStackGroup")
                rv.commands.setNodeInputs(stack_node, source_groups)
                rv.commands.setStringProperty(f"{stack_node}.ui.name", [f"{ext}_stack({version_comparison})"])
                stack_nodes.append(stack_node)
                
                # Create layout
                layout_node = rv.commands.newNode("RVLayoutGroup")
                rv.commands.setNodeInputs(layout_node, source_groups)
                rv.commands.setStringProperty(f"{layout_node}.layout.mode", ["packed"])
                rv.commands.setStringProperty(f"{layout_node}.ui.name", [f"{ext}_layout({version_comparison})"])
            else:
                # Single representation, just load it
                OpenRVStackHandler._load_representation(contexts[0])
        
        # Set view to first stack if any
        if stack_nodes:
            rv.commands.setViewNode(stack_nodes[0])
            rv.commands.setFrame(1)
        
        return True
    
    @staticmethod
    def _group_by_extension(context, ext_groups):
        """Group representation by extension"""
        filepath = get_representation_path(context["representation"])
        ext = os.path.splitext(filepath)[1].lower()
        ext_groups[ext].append(context)
    
    @staticmethod
    def _load_representation(context):
        """Load single representation and return node"""
        filepath = get_representation_path(context["representation"])
        
        ext = os.path.splitext(filepath)[1].lower()
        if ext in [".mov", ".mp4"]:
            final_path = filepath
        else:
            final_path = rv.commands.sequenceOfFile(filepath)[0]
        
        loaded_node = rv.commands.addSourceVerbose([final_path])
        
        rep_name = os.path.basename(final_path)
        namespace = context["folder"]["name"]
        
        imprint_container(
            loaded_node,
            name=rep_name,
            namespace=namespace,
            context=context,
            loader="OpenRVStackHandler"
        )
        
        return loaded_node
    
    @staticmethod
    def _prepare_load_path(path):
        """Prepare path for RV loading (handle sequences)"""
        import re
        from pathlib import Path
        
        ext = Path(path).suffix.lower()
        
        if ext in ['.exr', '.jpg', '.jpeg', '.png', '.tiff', '.dpx']:
            folder = os.path.dirname(path)
            filename = os.path.basename(path)
            
            match = re.match(r"^(.*?)(\d+)(\.[^.]+)$", filename)
            if match and os.path.exists(folder):
                prefix, frame_str, ext = match.groups()
                frames = []
                
                for f in os.listdir(folder):
                    m = re.match(rf"^{re.escape(prefix)}(\d+){re.escape(ext)}$", f)
                    if m:
                        frames.append(int(m.group(1)))
                
                if frames:
                    start, end = min(frames), max(frames)
                    return os.path.join(folder, f"{prefix}{start}-{end}#{ext}")
        
        return path