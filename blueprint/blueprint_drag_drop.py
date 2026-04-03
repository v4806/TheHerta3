import bpy
from ..config.main_config import GlobalConfig
from ..utils.collection_utils import CollectionUtils
from .blueprint_node_obj import _is_viewing_group_objects


_object_to_node_mapping = {}
_node_to_object_id_mapping = {}
_is_importing = False
_syncing_selection = False
_node_selection_timer = None
_object_name_check_timer = None
_last_node_selection_state = {}
_last_synced_object = None
_cleanup_counter = 0
_sync_from_nodes = False


@bpy.app.handlers.persistent
def object_visibility_handler(scene):
    """处理物体可见性变化事件，同步更新对应节点的禁用状态"""
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    obj_name = getattr(node, 'object_name', '')
                    if obj_name:
                        obj = bpy.data.objects.get(obj_name)
                        if obj:
                            current_mute = obj.hide_viewport
                            if node.mute != current_mute:
                                node.mute = current_mute


@bpy.app.handlers.persistent
def object_selection_handler(scene):
    """处理物体选中状态变化事件，同步更新对应节点的选中状态"""
    global _syncing_selection, _last_synced_object, _sync_from_nodes
    
    if _syncing_selection:
        return
    
    if _is_viewing_group_objects:
        return
    
    if _sync_from_nodes:
        _sync_from_nodes = False
        return
    
    _syncing_selection = True
    
    try:
        for tree in bpy.data.node_groups:
            if tree.bl_idname == 'SSMTBlueprintTreeType':
                for node in tree.nodes:
                    if node.bl_idname == 'SSMTNode_Object_Info':
                        obj_name = getattr(node, 'object_name', '')
                        if obj_name:
                            obj = bpy.data.objects.get(obj_name)
                            if obj:
                                current_select = obj.select_get()
                                if node.select != current_select:
                                    node.select = current_select
    finally:
        _syncing_selection = False


def _initialize_workspace_cache():
    """初始化工作合集中物体的缓存"""
    global _object_to_node_mapping, _node_to_object_id_mapping, _is_importing
    
    _object_to_node_mapping = {}
    _node_to_object_id_mapping = {}
    _is_importing = False
    
    _initialize_node_object_ids()
    _build_object_to_node_mapping()
    _update_node_to_object_id_mapping()


def _initialize_node_object_ids():
    """为旧工程中的节点初始化物体ID，建立节点与物体的关联"""
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    obj_name = getattr(node, 'object_name', '')
                    obj_id = getattr(node, 'object_id', '')
                    
                    if obj_name and not obj_id:
                        obj = bpy.data.objects.get(obj_name)
                        if obj:
                            node.object_id = str(obj.as_pointer())


def _update_node_to_object_id_mapping():
    """更新节点到物体ID的映射关系"""
    global _node_to_object_id_mapping
    _node_to_object_id_mapping = {}
    
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    obj_id = getattr(node, 'object_id', '')
                    if obj_id:
                        node_key = (tree.name, node.name)
                        _node_to_object_id_mapping[node_key] = obj_id


def _cleanup_invalid_mappings():
    """清理无效的映射关系"""
    global _object_to_node_mapping
    
    valid_object_names = set(obj.name for obj in bpy.data.objects)
    keys_to_remove = []
    
    for obj_name in _object_to_node_mapping:
        if obj_name not in valid_object_names:
            keys_to_remove.append(obj_name)
    
    for key in keys_to_remove:
        del _object_to_node_mapping[key]


def _build_object_to_node_mapping():
    """构建物体到节点的映射关系"""
    global _object_to_node_mapping
    _object_to_node_mapping = {}
    
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    obj_name = getattr(node, 'object_name', '')
                    if obj_name:
                        _object_to_node_mapping[obj_name] = node


def set_importing_state(is_importing):
    """设置导入状态，避免导入时触发自动节点创建"""
    global _is_importing
    _is_importing = is_importing


def refresh_workspace_cache():
    """刷新工作合集中物体的缓存，用于导入完成后调用"""
    global _is_importing
    set_importing_state(False)
    _initialize_workspace_cache()


def sync_node_selection_to_objects():
    """同步节点选中状态到物体，当节点选中状态变化时调用"""
    global _syncing_selection, _sync_from_nodes
    
    if _syncing_selection:
        return
    
    _sync_from_nodes = True
    _syncing_selection = True
    
    try:
        for tree in bpy.data.node_groups:
            if tree.bl_idname == 'SSMTBlueprintTreeType':
                for node in tree.nodes:
                    if node.bl_idname == 'SSMTNode_Object_Info':
                        obj_name = getattr(node, 'object_name', '')
                        if obj_name:
                            obj = bpy.data.objects.get(obj_name)
                            if obj:
                                obj.select_set(node.select)
    finally:
        _syncing_selection = False


def check_node_selection_changes():
    """定时检查节点选中状态变化，并同步到物体"""
    global _last_node_selection_state, _syncing_selection, _last_synced_object, _cleanup_counter, _sync_from_nodes
    
    if _syncing_selection:
        return 0.1
    
    if _is_viewing_group_objects:
        return 0.1
    
    _cleanup_counter += 1
    if _cleanup_counter >= 600:
        _cleanup_counter = 0
        _cleanup_invalid_mappings()
    
    changed_nodes = []
    current_node_keys = set()
    
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    node_key = (tree.name, node.name)
                    current_node_keys.add(node_key)
                    current_select = node.select
                    
                    if node_key in _last_node_selection_state:
                        if _last_node_selection_state[node_key] != current_select:
                            changed_nodes.append(node)
                            _last_node_selection_state[node_key] = current_select
                    else:
                        _last_node_selection_state[node_key] = current_select
    
    keys_to_remove = set(_last_node_selection_state.keys()) - current_node_keys
    for key in keys_to_remove:
        del _last_node_selection_state[key]
    
    if changed_nodes:
        _sync_from_nodes = True
        _syncing_selection = True
        try:
            object_to_nodes_map = {}
            for node in changed_nodes:
                obj_name = getattr(node, 'object_name', '')
                if obj_name:
                    if obj_name not in object_to_nodes_map:
                        object_to_nodes_map[obj_name] = []
                    object_to_nodes_map[obj_name].append(node)
            
            for obj_name, nodes in object_to_nodes_map.items():
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    select_state = any(node.select for node in nodes)
                    obj.select_set(select_state)
                    for node in nodes:
                        node.select = select_state
        finally:
            _syncing_selection = False
    
    return 0.1


def check_object_name_changes():
    """定时检查物体名称变化，并更新对应节点的物体引用"""
    global _node_to_object_id_mapping, _object_to_node_mapping
    
    object_id_to_name = {str(obj.as_pointer()): obj.name for obj in bpy.data.objects}
    
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'SSMTBlueprintTreeType':
            for node in tree.nodes:
                if node.bl_idname == 'SSMTNode_Object_Info':
                    obj_id = getattr(node, 'object_id', '')
                    if not obj_id:
                        continue
                    
                    obj_name = getattr(node, 'object_name', '')
                    if not obj_name:
                        continue
                    
                    current_obj = bpy.data.objects.get(obj_name)
                    if current_obj and str(current_obj.as_pointer()) == obj_id:
                        continue
                    
                    if obj_id in object_id_to_name:
                        new_name = object_id_to_name[obj_id]
                        if node.object_name != new_name:
                            old_name = node.object_name
                            node.object_name = new_name
                            
                            if old_name in _object_to_node_mapping:
                                del _object_to_node_mapping[old_name]
                            _object_to_node_mapping[new_name] = node
                elif node.bl_idname == 'SSMTNode_MultiFile_Export':
                    for item in node.object_list:
                        obj_name = getattr(item, 'object_name', '')
                        if not obj_name:
                            continue
                        
                        current_obj = bpy.data.objects.get(obj_name)
                        if current_obj:
                            new_name = current_obj.name
                            if item.object_name != new_name:
                                item.object_name = new_name
    
    return 2.0


def register():
    global _node_selection_timer, _object_name_check_timer
    bpy.app.handlers.depsgraph_update_post.append(object_visibility_handler)
    bpy.app.handlers.depsgraph_update_post.append(object_selection_handler)
    
    _node_selection_timer = bpy.app.timers.register(check_node_selection_changes, persistent=True)
    _object_name_check_timer = bpy.app.timers.register(check_object_name_changes, persistent=True)
    
    bpy.app.timers.register(_initialize_workspace_cache, first_interval=0.1)


def unregister():
    global _node_selection_timer, _object_name_check_timer
    if _node_selection_timer:
        try:
            bpy.app.timers.unregister(_node_selection_timer)
        except:
            pass
        _node_selection_timer = None
    
    if _object_name_check_timer:
        try:
            bpy.app.timers.unregister(_object_name_check_timer)
        except:
            pass
        _object_name_check_timer = None
    
    if object_visibility_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(object_visibility_handler)
    if object_selection_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(object_selection_handler)
    
    global _object_to_node_mapping, _node_to_object_id_mapping, _is_importing, _syncing_selection, _last_node_selection_state, _cleanup_counter
    _object_to_node_mapping = {}
    _node_to_object_id_mapping = {}
    _is_importing = False
    _syncing_selection = False
    _last_node_selection_state = {}
    _cleanup_counter = 0
