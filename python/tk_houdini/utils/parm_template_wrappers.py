from __future__ import print_function


import sgtk


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
    def from_template(cls, template, parent=None):
        """
        Method to build a Parm object from a given template.

        :param template: A :class:`hou.ParmTemplate` instance.
        :param Parm parent : The parent object.

        :returns: A :class:`Parm` or :class:`ParmFolder` instance.
        """
        import hou

        if template.type() == hou.parmTemplateType.Folder:
            return ParmFolder(template, parent=parent)
        return Parm(template, parent=parent)

    def __init__(self, template, parent=None):
        """
        Initialise the class.

        :param template: A :class:`hou.ParmTemplate` instance.
        :param Parm parent : The parent object.
        """
        self.template = template
        self.parent = parent
        self.logger = sgtk.platform.get_logger(__name__)

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

    def __init__(self, template, parent=None):
        """
        Initialise the class.

        :param template: A :class:`hou.ParmTemplate` instance.
        :param Parm parent : The parent object.
        """
        super(ParmFolder, self).__init__(template, parent=parent)
        self.__children = [
            Parm.from_template(child) for child in template.parmTemplates()
        ]
        self.__child_names = [child.name for child in self.__children]

    @property
    def descendents(self):
        """
        Get the descendent templates from this object.

        :rtype: list(Parm)
        """
        descendents = []
        for child in self:
            descendents.append(child)
            if isinstance(child, ParmFolder):
                descendents.extend(child.descendents)
        return descendents

    def get_root(self):
        """
        Get the root item this object belongs to.

        :returns: The top most parent :class:`ParmGroup` instance.
        """
        parent = current = self
        while current.parent:
            parent = current
        return parent

    def _remove_existing_children(self, parm, root):
        """
        Removes all child :class:`Parm` objects from the given :class:`Parm` that
        already exist within the node template hierarchy.

        :param Parm parm: The :class:`Parm` to check.
        :param root parm: The highest level :class:`Parm` object that the given
            :class:`Parm` will belong to.
        """
        for child in parm:
            if child.name in root:
                self.logger.debug("Parm %r already exists. Skipping", child.name)
                index = parm.index_of_template(child.name)
                parm.pop_template(index)
            elif isinstance(child, ParmFolder):
                self._remove_existing_children(child, root)

    def remove_existing(self, parm):
        """
        Removes all instances of existing templates in the given :class:`Parm`
        that already exist within the hierarchy.

        If the :class:`Parm` itself is a duplicate, then this method retuns `None`
        and the item is not added to the overall template.

        :param Parm parm: The :class:`Parm` to check.

        :returns: A sanitised :class:`Parm` or :class:`NoneType`
        """
        root = self.get_root()
        if parm.name in root:
            self.logger.debug("Parm %r already exists. Skipping", parm.name)
            return None
        elif isinstance(parm, ParmFolder):
            self._remove_existing_children(parm, root)
        return parm

    def index_of_template(self, template_name):
        """
        Get the index of the child template from the list of child templates.

        :param str template_name: The name of the template to find.
        :rtype: int
        """
        return self.__child_names.index(template_name)

    def extend(self, parms):
        """
        Add multiple templates to the child templates list..

        :param list(Parm)) parms: The list of Parm
            instances to add.
        """
        for parm in parms:
            self.append(parm)

    __iadd__ = extend

    def extend_templates(self, templates):
        """
        Add multiple templates to the child templates list..

        :param list(hou.ParmTemplate) templates: The list of template
            instances to add.
        """
        self.extend(Parm.from_template(template, parent=self) for template in templates)

    def append(self, parm):
        """
        Add a template to the child templates list.

        :param Parm parm: The Parm to add.
        """
        parm = self.remove_existing(parm)
        if parm:
            parm.parent = self
            self.__child_names.append(parm.name)
            self.__children.append(parm)

    def append_template(self, template):
        """
        Add a template to the child templates list.

        :param hou.ParmTemplate template: The template to add.
        """
        self.append(Parm.from_template(template, parent=self))

    def insert(self, index, parm):
        """
        Insert a template into the child templates list.

        :param int index: The position to add the template.
        :param Parm parm: The Parm to insert.
        """
        parm = self.remove_existing(parm)
        if parm:
            parm.parent = self
            self.__child_names.insert(index, parm.name)
            self.__children.insert(index, parm)

    def insert_template(self, index, template):
        """
        Insert a template into the child templates list.

        :param int index: The position to add the template.
        :param hou.ParmTemplate template: The template to insert.
        """
        parm = Parm.from_template(template, parent=self)
        self.insert(index, parm)

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
        return name in [item.name for item in self.descendents]

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
