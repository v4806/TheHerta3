from dataclasses import dataclass, field


class M_DrawIndexed:
    def __init__(self) -> None:
        self.DrawNumber = ""
        self.DrawOffsetIndex = "" 
        self.DrawStartIndex = "0"
        self.AliasName = "" 
        self.UniqueVertexCount = 0 
    
    def get_draw_str(self) -> str:
        return "drawindexed = " + self.DrawNumber + "," + self.DrawOffsetIndex + "," + self.DrawStartIndex

@dataclass
class M_DrawIndexedInstanced:
    IndexCountPerInstance: int = field(init=False, repr=False, default=0)
    InstanceCount: int = field(init=False, repr=False, default=0)
    StartIndexLocation: int = field(init=False, repr=False, default=0)
    BaseVertexLocation: int = field(init=False, repr=False, default=0)
    StartInstanceLocation: int = field(init=False, repr=False, default=0)

    def get_draw_str(self) -> str:
        draw_str = "drawindexedinstanced = "
        draw_str += str(self.IndexCountPerInstance) + ","
        if self.InstanceCount == 0:
            draw_str += "INSTANCE_COUNT,"
        else:
            draw_str += str(self.InstanceCount) + ","
        draw_str += str(self.StartIndexLocation) + ","
        draw_str += str(self.BaseVertexLocation) + ","
        if self.StartInstanceLocation == 0:
            draw_str += "FIRST_INSTANCE"
        else:
            draw_str += str(self.StartInstanceLocation)
        return draw_str

class M_Condition:
    def __init__(self, work_key_list: list = []):
        self.work_key_list = work_key_list
        condition_str = ""
        if len(self.work_key_list) != 0:
            for work_key in self.work_key_list:
                single_condition: str = work_key.key_name + " == " + str(work_key.tmp_value)
                condition_str = condition_str + single_condition + " && "
            condition_str = condition_str[:-4]
        self.condition_str = condition_str

class ObjRuleName:
    def __init__(self, obj_name: str):
        self.obj_name = obj_name
        self.draw_ib = ""
        self.index_count = ""
        self.first_index = ""
        self.obj_alias_name = ""
        self.objname_parse_error_tips = "Obj名称规则为: DrawIB-IndexCount-FirstIndex.AliasName,例如[67f829fc-2653-0.头发]第一个.前面的内容要符合规则,后面出现的内容是可以自定义的"
        
        if "." in self.obj_name:
            obj_name_total_split = self.obj_name.split(".")
            obj_name_split = obj_name_total_split[0].split("-")
            
            if len(obj_name_total_split) < 2:
                raise Exception("Obj名称解析错误: " + self.obj_name + "  不包含'.'分隔符\n" + self.objname_parse_error_tips)
            self.obj_alias_name = ".".join(obj_name_total_split[1:]) if len(obj_name_total_split) > 1 else ""
            if len(obj_name_split) < 3:
                raise Exception("Obj名称解析错误: " + self.obj_name + "  '-'分隔符数量不足，至少需要2个\n" + self.objname_parse_error_tips)
            else:
                self.draw_ib = obj_name_split[0]
                self.index_count = obj_name_split[1]
                self.first_index = obj_name_split[2]
        else:
            raise Exception("Obj名称解析错误: " + self.obj_name + "  不包含'.'分隔符\n" + self.objname_parse_error_tips)

@dataclass
class DrawCallModel:
    obj_name: str
    match_draw_ib: str = field(init=False, repr=False, default="")
    match_index_count: str = field(init=False, repr=False, default="")
    match_first_index: str = field(init=False, repr=False, default="")
    comment_alias_name: str = field(init=False, repr=False, default="")
    display_name: str = field(init=False, repr=False, default="")
    condition: M_Condition = field(init=False, repr=False, default_factory=M_Condition)
    index_count: int = field(init=False, repr=False, default=0)
    vertex_count: int = field(init=False, repr=False, default=0)
    index_offset: int = field(init=False, repr=False, default=0)

    def __post_init__(self):
        obj_rule_name = ObjRuleName(self.obj_name)
        self.match_draw_ib = obj_rule_name.draw_ib
        self.match_index_count = obj_rule_name.index_count
        self.match_first_index = obj_rule_name.first_index
        self.comment_alias_name = obj_rule_name.obj_alias_name
        self.display_name = self.obj_name
    
    def get_unique_str(self) -> str:
        return self.match_draw_ib + "-" + self.match_index_count + "-" + self.match_first_index
