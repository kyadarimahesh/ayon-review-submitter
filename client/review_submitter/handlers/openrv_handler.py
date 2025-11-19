import os
import re
from collections import defaultdict
from pathlib import Path

try:
    import rv.commands
except ImportError:
    rv = None

import ayon_api
from ayon_core.pipeline.load import get_representation_path

try:
    from ayon_openrv.api.pipeline import imprint_container
except ImportError:
    imprint_container = None


class OpenRVStackHandler:
    """Handler for creating AUTO stack in OpenRV"""
    
    @staticmethod
    def create_auto_stack(context):
        """Create AUTO stack in OpenRV for the given context"""
        if rv is None:
            print("RV module not available")
            return False
        
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
                    try:
                        filepath = get_representation_path(ctx["representation"])
                        load_path = OpenRVStackHandler._prepare_load_path(filepath)
                        
                        # Load using addSourcesVerbose for proper group handling
                        nodes = rv.commands.addSourcesVerbose([[load_path]])
                        if nodes:
                            source_group = rv.commands.nodeGroup(nodes[0])
                            source_groups.append(source_group)
                            version_names.append(ctx["version"]["name"])
                            
                            # Store version_id in source for later retrieval
                            OpenRVStackHandler._store_version_metadata(source_group, ctx)
                            print(f"Loaded {ctx['version']['name']} for stack")
                        else:
                            print(f"Warning: Failed to load {filepath}")
                    except Exception as e:
                        print(f"Error loading representation: {e}")
                        continue
                
                # Create version comparison name
                version_comparison = "/".join(version_names)
                
                if source_groups:
                    # Create stack
                    stack_node = rv.commands.newNode("RVStackGroup")
                    rv.commands.setNodeInputs(stack_node, source_groups)
                    rv.commands.setStringProperty(f"{stack_node}.ui.name", [f"{ext}_stack({version_comparison})"])
                    stack_nodes.append(stack_node)
                    print(f"Created stack: {ext}_stack({version_comparison})")
                    
                    # Create layout
                    layout_node = rv.commands.newNode("RVLayoutGroup")
                    rv.commands.setNodeInputs(layout_node, source_groups)
                    rv.commands.setStringProperty(f"{layout_node}.layout.mode", ["packed"])
                    rv.commands.setStringProperty(f"{layout_node}.ui.name", [f"{ext}_layout({version_comparison})"]) 
                    print(f"Created layout: {ext}_layout({version_comparison})")
                else:
                    print(f"Warning: No sources loaded for {ext} extension")
            else:
                # Single representation, just load it
                try:
                    OpenRVStackHandler._load_representation(contexts[0])
                    print(f"Loaded single representation for {ext}")
                except Exception as e:
                    print(f"Error loading single representation: {e}")
        
        # Set view to first stack if any
        if stack_nodes:
            try:
                rv.commands.setViewNode(stack_nodes[0])
                rv.commands.setFrame(1)
                print(f"Set view to first stack, total stacks created: {len(stack_nodes)}")
            except Exception as e:
                print(f"Warning: Could not set view to stack: {e}")
        
        print("OpenRV stack creation completed successfully")
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
        load_path = OpenRVStackHandler._prepare_load_path(filepath)
        
        loaded_node = rv.commands.addSourceVerbose([load_path])
        
        rep_name = os.path.basename(filepath)
        namespace = context.get("folder", {}).get("name", "default")
        
        # Store version_id in source
        OpenRVStackHandler._store_version_metadata(loaded_node, context)
        
        if imprint_container:
            imprint_container(
                loaded_node,
                name=rep_name,
                namespace=namespace,
                context=context,
                loader="OpenRVStackHandler"
            )
        
        return loaded_node
    
    @staticmethod
    def read_version_metadata_from_rv():
        """Read version_id from all sources in current RV session"""
        if rv is None:
            return {}
        
        source_mapping = {}
        try:
            sources = rv.commands.nodesOfType("RVSourceGroup")
            for source in sources:
                version_id_prop = f"{source}.ayon.version_id"
                representation_id_prop = f"{source}.ayon.representation_id"
                filepath_prop = f"{source}.ayon.file_path"
                
                if rv.commands.propertyExists(version_id_prop):
                    version_id = rv.commands.getStringProperty(version_id_prop)[0]
                    representation_id = None
                    filepath = None
                    
                    if rv.commands.propertyExists(representation_id_prop):
                        representation_id = rv.commands.getStringProperty(representation_id_prop)[0]
                    
                    if rv.commands.propertyExists(filepath_prop):
                        filepath = rv.commands.getStringProperty(filepath_prop)[0]
                    
                    source_mapping[source] = {
                        'version_id': version_id,
                        'representation_id': representation_id,
                        'path': filepath
                    }
                    print(f"Found version metadata in {source}: {version_id}")
        
        except Exception as e:
            print(f"Error reading version metadata: {e}")
        
        return source_mapping
    
    @staticmethod
    def _store_version_metadata(node, context):
        """Store version_id and related metadata in RV source node"""
        if rv is None:
            return
        
        try:
            version_id = context.get("version", {}).get("id")
            representation_id = context.get("representation", {}).get("id")
            
            if version_id:
                prop = f"{node}.ayon.version_id"
                if not rv.commands.propertyExists(prop):
                    rv.commands.newProperty(prop, rv.commands.StringType, 1)
                rv.commands.setStringProperty(prop, [version_id], True)
            
            if representation_id:
                prop = f"{node}.ayon.representation_id"
                if not rv.commands.propertyExists(prop):
                    rv.commands.newProperty(prop, rv.commands.StringType, 1)
                rv.commands.setStringProperty(prop, [representation_id], True)
            
            # Store file path
            filepath = get_representation_path(context["representation"])
            prop = f"{node}.ayon.file_path"
            if not rv.commands.propertyExists(prop):
                rv.commands.newProperty(prop, rv.commands.StringType, 1)
            rv.commands.setStringProperty(prop, [filepath], True)
            
        except Exception as e:
            print(f"Warning: Could not store version metadata: {e}")
    
    @staticmethod
    def _prepare_load_path(path):
        """Prepare path for RV loading (handle sequences)"""
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