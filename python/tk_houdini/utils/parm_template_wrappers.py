def wrap_node_parameter_group(node):
    template_group = node.parmTemplateGroup()
    parameter_group = ParmGroup(template_group)
    return parameter_group


class Parm(object):
    @classmethod
    def build_parm(cls, template):
        import hou
        if template.type() == hou.parmTemplateType.Folder:
            return ParmFolder(template)
        return Parm(template)

    def __init__(self, template):
        self.template = template
        
    @property
    def name(self):
        return self.template.name()
        
    def build(self):
        return self.template
        
    def dumps(self, indent=0):
        print "\t"*indent, self.template


class ParmFolder(Parm):
    def __init__(self, template):
        super(ParmFolder, self).__init__(template)
        self.__children = [Parm.build_parm(child) for child in template.parmTemplates()]
        self.__child_names = [child.name for child in self.__children]
        
    def index_of_template(self, template_name):
        return self.__child_names.index(template_name)
        
    def extend_templates(self, templates):
        template_names = [template.name() for template in templates]
        child_templates = [Parm.build_parm(template) for template in templates]
        self.__child_names.extend(template_names)
        self.__children.extend(child_templates)
        
    def append_template(self, template):
        self.extend_templates([template])
        
    def insert_template(self, index, template):
        template_name = template.name()
        self.__child_names.insert(index, template_name)
        parm = Parm.build_parm(template)
        self.__children.insert(index, parm)

    def pop_template(self, index):
        self.__child_names.pop(index)
        return self.__children.pop(index).template
        
    def get(self, template_name):
        index_of_template = self.__child_names.index(template_name)
        return self.__children[index_of_template]
        
    def __iter__(self):
        return iter(self.__children)
        
    def __len__(self):
        return len(self.__children)

    def __contains__(self, name):
        return name in self.__child_names
        
    def _child_templates(self):
        return [child.build() for child in self]
        
    def build(self):
        new_template = self.template.clone()
        new_template.setParmTemplates(self._child_templates())
        return new_template
        
    def dumps(self, indent=0):
        print "\t"*indent, self.template
        indent += 1
        for child in self.__children:
            child.dumps(indent)


class ParmGroup(ParmFolder):
    def build(self):
        import hou
        return hou.ParmTemplateGroup(self._child_templates())
        
    @property
    def name(self):
        return "ParmTemplateGroup"
