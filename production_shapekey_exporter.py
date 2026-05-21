bl_info = {
    "name": "Production Shapekey & Web Exporter",
    "author": "Yuriy3D",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Production",
    "description": "Comprehensive pipeline toolkit for shapekeys matching, active syncing, test linking, material merging, and smart GLTF/GLB web-export.",
    "category": "Object",
}

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty

# --- 1. OPERATOR: COPY SHAPEKEY NAMES ---
class OBJECT_OT_copy_shape_names(bpy.types.Operator):
    """Copy only shapekey names from the active object to all other selected meshes"""
    bl_idname = "object.copy_shape_names"
    bl_label = "Copy Shapekey Names"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        source = context.active_object
        if not source or not source.data or not source.data.shape_keys:
            self.report({'WARNING'}, "Active object has no shapekeys!")
            return {'CANCELLED'}
        source_keys = [key.name for key in source.data.shape_keys.key_blocks]
        for obj in context.selected_objects:
            if obj != source and obj.type == 'MESH':
                if not obj.data.shape_keys:
                    obj.shape_key_add(name="Basis")
                for name in source_keys:
                    if name not in obj.data.shape_keys.key_blocks:
                        obj.shape_key_add(name=name)
        self.report({'INFO'}, f"Shapekey names successfully copied from {source.name}")
        return {'FINISHED'}


# --- 2. OPERATOR: SET ACTIVE SHAPEKEY TO SELECTED ---
class OBJECT_OT_sync_active_shapekey(bpy.types.Operator):
    """Switch active shapekey index on all selected meshes to match the active object's selection"""
    bl_idname = "object.sync_active_shapekey"
    bl_label = "Set Active Shapekey to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        source = context.active_object
        if not source or not source.data or not source.data.shape_keys or not source.active_shape_key:
            self.report({'WARNING'}, "No active shapekey selected on the main object!")
            return {'CANCELLED'}
            
        target_name = source.active_shape_key.name
        success_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.data.shape_keys:
                kb = obj.data.shape_keys.key_blocks
                if target_name in kb:
                    obj.active_shape_key_index = kb.find(target_name)
                    success_count += 1
        self.report({'INFO'}, f"Shapekey '{target_name}' activated on {success_count} objects")
        return {'FINISHED'}


# --- 3. OPERATOR: LINK SHAPEKEY VALUES (FIXED STABLE INDEX FOR BLENDER 4.x) ---
class OBJECT_OT_link_shapekey_drivers(bpy.types.Operator):
    """Link matching shapekeys from selected objects to the active object via Blender Drivers for visual testing"""
    bl_idname = "object.link_shapekey_drivers"
    bl_label = "Link Shapekey Values (Test)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        source = context.active_object
        if not source or not source.data or not source.data.shape_keys:
            self.report({'WARNING'}, "Main controller object has no shapekeys!")
            return {'CANCELLED'}
        source_keys = source.data.shape_keys
        for obj in context.selected_objects:
            if obj == source or obj.type != 'MESH' or not obj.data.shape_keys:
                continue
            target_keys = obj.data.shape_keys
            for key_block in target_keys.key_blocks:
                name = key_block.name
                if name == "Basis":
                    continue
                if name in source_keys.key_blocks:
                    try:
                        target_keys.animation_data.drivers.remove(
                            target_keys.driver_data_get(f'key_blocks["{name}"].value')
                        )
                    except:
                        pass
                    path = f'key_blocks["{name}"].value'
                    driver_info = target_keys.driver_add(path)
                    drv = driver_info.driver
                    drv.type = 'AVERAGE'
                    
                    var = drv.variables.new()
                    var.name = "value"
                    var.type = 'SINGLE_PROP'
                    
                    # BLENDER 4.x SYNTAX: Use the predefined single target slot
                    target = var.targets[0]
                    target.id_type = 'KEY'
                    target.id = source_keys
                    target.data_path = f'key_blocks["{name}"].value'
                    
        self.report({'INFO'}, f"Visual synchronization enabled for {source.name}")
        return {'FINISHED'}


# --- 4. OPERATOR: CLEAR SHAPEKEY DRIVERS ---
class OBJECT_OT_clear_shapekey_drivers(bpy.types.Operator):
    """Remove all testing drivers from selected objects to prepare models for clean production export"""
    bl_idname = "object.clear_shapekey_drivers"
    bl_label = "Clear Shapekey Drivers"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cleared_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.data.shape_keys:
                key_data = obj.data.shape_keys
                if key_data.animation_data and key_data.animation_data.drivers:
                    shape_drivers = [d for d in key_data.animation_data.drivers if "key_blocks" in d.data_path]
                    for d in shape_drivers:
                        key_data.animation_data.drivers.remove(d)
                        cleared_count += 1
        self.report({'INFO'}, f"Cleared {cleared_count} drivers. Models are ready for clean production.")
        return {'FINISHED'}


# --- 5. OPERATOR: PURGE UNUSED SHAPEKEYS ---
class OBJECT_OT_delete_empty_shapekeys(bpy.types.Operator):
    """Delete shapekeys that do not deform mesh vertices relative to the Basis key"""
    bl_idname = "object.delete_empty_shapekeys"
    bl_label = "Delete Empty Shapekeys"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        total_deleted = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH' or not obj.data.shape_keys:
                continue
            shape_keys = obj.data.shape_keys
            basis_block = shape_keys.reference_key
            if not basis_block:
                continue
            basis_data = basis_block.data
            num_verts = len(basis_data)
            to_delete = []
            for kb in shape_keys.key_blocks:
                if kb == basis_block:
                    continue
                is_empty = True
                kb_data = kb.data
                for i in range(num_verts):
                    if (kb_data[i].co - basis_data[i].co).length > 0.00001:
                        is_empty = False
                        break
                if is_empty:
                    to_delete.append(kb)
            for kb in to_delete:
                obj.shape_key_remove(kb)
                total_deleted += 1
        self.report({'INFO'}, f"Removed {total_deleted} empty shapekeys.")
        return {'FINISHED'}


# --- 6. OPERATOR: MERGE DUPLICATE MATERIALS ---
class OBJECT_OT_merge_duplicate_materials(bpy.types.Operator):
    """Find dot-suffixed duplicate materials (.001, .002) and remap them to the originals across the scene"""
    bl_idname = "object.merge_duplicate_materials"
    bl_label = "Merge Duplicate Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        materials = bpy.data.materials
        remap_dict = {}
        
        for mat in materials:
            if len(mat.name) > 4 and mat.name[-4] == "." and mat.name[-3:].isdigit():
                base_name = mat.name[:-4]
                if base_name in materials:
                    remap_dict[mat] = materials[base_name]
                    
        if not remap_dict:
            self.report({'INFO'}, "No duplicate materials found.")
            return {'FINISHED'}
            
        merged_count = len(remap_dict)
        for old_mat, new_mat in remap_dict.items():
            old_mat.user_remap(new_mat)
            materials.remove(old_mat)
            
        self.report({'INFO'}, f"Successfully merged and deleted {merged_count} duplicate materials.")
        return {'FINISHED'}


# --- 7. OPERATOR: SMART EXPORT BUTTON (OPENS NATIVE BLENDER EXPORT WINDOW) ---
class OBJECT_OT_export_optimized_glb(bpy.types.Operator):
    """Open native Blender glTF 2.0 export window with full original settings panel"""
    bl_idname = "object.export_optimized_glb"
    bl_label = "Export .GLB"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # This fallback is required for internal Blender execution flow
        return bpy.ops.export_scene.gltf('INVOKE_DEFAULT')

    def invoke(self, context, event):
        # Force Blender to open the standard file browser for glTF with all settings
        return bpy.ops.export_scene.gltf('INVOKE_DEFAULT')


# --- 8. UI PANEL IN N-PANEL ---
class VIEW3D_PT_production_toolkit(bpy.types.Panel):
    """Creates a Panel in the Visual 3D Viewport N-Panel"""
    bl_label = "Production Web Toolkit"
    bl_idname = "VIEW3D_PT_production_toolkit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Production'

    def draw(self, context):
        layout = self.layout
        
        # Shapekeys Management section
        box = layout.box()
        box.label(text="Shapekey Management", icon='SHAPEKEY_DATA')
        box.operator("object.copy_shape_names", icon='DUPLICATE')
        box.operator("object.sync_active_shapekey", icon='RESTRICT_SELECT_OFF')
        
        # Testing & Drivers section
        box = layout.box()
        box.label(text="Testing & Drivers", icon='DRIVER')
        box.operator("object.link_shapekey_drivers", icon='LINKED')
        box.operator("object.clear_shapekey_drivers", icon='X')
        
        # Geometry Optimization section
        box = layout.box()
        box.label(text="Geometry Optimization", icon='MESH_DATA')
        box.operator("object.delete_empty_shapekeys", icon='TRASH')
        
        # Scene & Materials Cleanup section
        box = layout.box()
        box.label(text="Scene Assets Cleanup", icon='ASSET_MANAGER')
        box.operator("object.merge_duplicate_materials", icon='MATERIAL')
        
        # Final Export section
        box = layout.box()
        box.label(text="Web Delivery (.glb)", icon='URL')
        box.operator("object.export_optimized_glb", icon='EXPORT')


# --- REGISTRATION ---
classes = (
    OBJECT_OT_copy_shape_names,
    OBJECT_OT_sync_active_shapekey,
    OBJECT_OT_link_shapekey_drivers,
    OBJECT_OT_clear_shapekey_drivers,
    OBJECT_OT_delete_empty_shapekeys,
    OBJECT_OT_merge_duplicate_materials,
    OBJECT_OT_export_optimized_glb,
    VIEW3D_PT_production_toolkit,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
