from __future__ import print_function


def wrap_node_parameter_group(node):
    """
    Helper function to convert a node's parameter group into
    a ParmGroup instance.

    :param node: A :class:`hou.Node` instance.

    :returns: A :class:`ParmGroup` instance.
    """
    template_group = node.parmTemplateGroup()
    parameter_group = ParmGroup(template_group)
    return parameter_group


class Parm(object):
    """
    Wrapper class for houdini parameter template instances.
    """

    @classmethod
    def build_parm(cls, template):
        """
        Method to build a Parm object from a given template.

        :param template: A :class:`hou.ParmTemplate` instance.

        :returns: A :class:`Parm` or :class:`ParmFolder` instance.
        """
        import hou

        if template.type() == hou.parmTemplateType.Folder:
            return ParmFolder(template)
        return Parm(template)

    def __init__(self, template):
        """
        Initialise the class.

        :param template: A :class:`hou.ParmTemplate` instance.
        """
        self.template = template

    @property
    def name(self):
        """
        Get the template name.

        :rtype: str
        """
        return self.template.name()

    def build(self):
        """
        Get the template relating to this Parm object.

        :rtype: :class:`hou.ParmTemplate`
        """
        return self.template

    def dumps(self, indent=0):
        """
        Dump a string representation of this object for debugging.

        :param int indent: Size of indenation.
        """
        print("\t" * indent, self.template)


class ParmFolder(Parm):
    """
    Wrapper class for houdini folder parameter template instances.
    """

    def __init__(self, template):
        """
        Initialise the class.

        :param template: A :class:`hou.ParmTemplate` instance.
        """
        super(ParmFolder, self).__init__(template)
        self.__children = [Parm.build_parm(child) for child in template.parmTemplates()]
        self.__child_names = [child.name for child in self.__children]

    def index_of_template(self, template_name):
        """
        Get the index of the child template from the list of child templates.

        :param str template_name: The name of the template to find.
        :rtype: int
        """
        return self.__child_names.index(template_name)

    def extend_templates(self, templates):
        """
        Add multiple templates to the child templates list..

        :param list(hou.ParmTemplate) templates: The list of template
            instances to add.
        """
        template_names = (template.name() for template in templates)
        child_templates = (Parm.build_parm(template) for template in templates)
        self.__child_names.extend(template_names)
        self.__children.extend(child_templates)

    def append_template(self, template):
        """
        Add a template to the child templates list.

        :param hou.ParmTemplate template: The template to add.
        """
        self.extend_templates([template])

    def insert_template(self, index, template):
        """
        Insert a template into the child templates list.

        :param int index: The position to add the template.
        :param hou.ParmTemplate template: The template to insert.
        """
        template_name = template.name()
        self.__child_names.insert(index, template_name)
        parm = Parm.build_parm(template)
        self.__children.insert(index, parm)

    def pop_template(self, index):
        """
        Pop a template from the child templates list.

        :param int index: The index of the child to pop.

        :rtype: A :class:`hou.ParmTemplate` instance.
        """
        self.__child_names.pop(index)
        return self.__children.pop(index).template

    def get(self, template_name):
        """
        Get a template from the child list by name of the template.

        :param str template_name: The name of the template to get.

        :rtype: A :class:`hou.ParmTemplate` instance.
        """
        index_of_template = self.__child_names.index(template_name)
        return self.__children[index_of_template]

    def __iter__(self):
        """
        Iterate through the children list.

        :rtype: Iterator
        """
        return iter(self.__children)

    def __len__(self):
        """
        Get the number of children.

        :rtype: int
        """
        return len(self.__children)

    def __contains__(self, name):
        """
        Find out if a template is contained in the list, by name:

        :param str name: The name of the template to check for.

        :rtype: bool
        """
        return name in self.__child_names

    def _child_templates(self):
        """
        Get the template hierarchy from the list of children.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        return [child.build() for child in self]

    def build(self):
        """
        Build the template hierarchy for this instance.

        :rtype: :class:`hou.ParmFolderTemplate`
        """
        new_template = self.template.clone()
        new_template.setParmTemplates(self._child_templates())
        return new_template

    def dumps(self, indent=0):
        print("\t" * indent, self.template)
        indent += 1
        for child in self.__children:
            child.dumps(indent)


class ParmGroup(ParmFolder):
    """
    Wrapper class for houdini parameter template group instances.
    """

    def build(self):
        """
        Build the template hierarchy for this instance.

        :rtype: :class:`hou.ParmTemplateGroup`
        """
        import hou

        return hou.ParmTemplateGroup(self._child_templates())

    @property
    def name(self):
        """
        Get the template name.

        :rtype: str
        """
        return "ParmTemplateGroup"
