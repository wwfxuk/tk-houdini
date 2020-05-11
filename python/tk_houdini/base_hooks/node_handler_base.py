"""
Implicit, base hook class for all node handlers.
"""

import itertools

import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class NodeHandlerBase(HookBaseClass):
    """
    Common base class for all node handlers.
    """

    NODE_TYPE = None
    NODE_CATEGORY = None

    VERSION_POLICIES = []

    SGTK_ALL_VERSIONS = "sgtk_all_versions"
    SGTK_VERSION = "sgtk_version"
    SGTK_REFRESH_VERSIONS = "sgtk_refresh_versions"
    SGTK_RESOLVED_VERSION = "sgtk_resolved_version"
    SGTK_FOLDER = "sgtk_folder"
    USE_SGTK = "use_sgtk"
    SGTK_IDENTIFIER = "sgtk_identifier"

    def __new__(cls, *args, **kwargs):
        """
        Set up the node handler class to contain the appropriate settings from the
        shotgun configs.

        We do this here as it only needs to happen on the first instantiation of
        a class type. When contexts change the modules are reloaded and this is
        wiped.

        Prevents us needing to define, in code, shotgun templates and settings.
        """
        if cls.NODE_TYPE and cls.NODE_CATEGORY:
            if hasattr(cls, "_work_template"):
                return super(NodeHandlerBase, cls).__new__(cls, *args, **kwargs)
            engine = sgtk.platform.current_engine()
            node_handlers = engine.get_setting("node_handlers")
            for handler in node_handlers:
                matching_node_category_type = (
                    handler["node_type"] == cls.NODE_TYPE
                    and handler["node_category"] == cls.NODE_CATEGORY
                )
                if matching_node_category_type :
                    work_template = engine.get_template_by_name(
                        handler["work_template"]
                    )
                    cls._work_template = work_template
                    publish_template = engine.get_template_by_name(
                        handler["publish_template"]
                    )
                    cls._publish_template = publish_template
                    cls.extra_args = handler["extra_args"]
                    engine.logger.debug(repr(handler))
                    break
        return super(NodeHandlerBase, cls).__new__(cls, *args, **kwargs)

    @staticmethod
    def generate_callback_script_str(method_name):
        """
        Helper function to generate a callback script string for houdini parameters.

        :param str method_name: The name of the method we want to be our callback.

        :rtype: str
        """
        callback_str = (
            "__import__('sgtk').platform.current_engine().node_handler(kwargs['node'])"
            ".{method}(kwargs)"
        ).format(method=method_name)
        return callback_str

    def get_work_template(self, node):
        """
        Get the shotgun work template for this node handler.

        :param node: A :class:`hou.Node` instance.

        :rtype: An :class:`sgtk.Template` instance.
        """
        return self._work_template

    def get_publish_template(self, node):
        """
        Get the shotgun publish template for this node handler.

        :param node: A :class:`hou.Node` instance.

        :rtype: An :class:`sgtk.Template` instance.
        """
        return self._publish_template

    def _get_template(self, template_name):
        """
        Get a shotgun template from the given name.

        :param str template_name: The name of the template to get.

        :rtype: An :class:`sgtk.Template` instance.

        :raises: :class:`sgtk.TankError` if no template name supplied
            or the template doesn't exist.
        """
        setting_template_name = self.extra_args.get(template_name)
        if not setting_template_name:
            raise sgtk.TankError(
                "No template name '{}' defined for node type '{}'"
                "".format(template_name, self.NODE_TYPE)
            )
        template = self.parent.get_template_by_name(setting_template_name)
        if not template:
            raise sgtk.TankError(
                "Can't find template called '{}' defined for node type '{}'"
                "".format(setting_template_name, self.NODE_TYPE)
            )
        return template

    ###########################################################################
    # Utilities
    ###########################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param ParmGroup parameter_group: The parameter group containing sgtk parameters.
        """
        raise NotImplementedError(
            "'_remove_sgtk_items_from_parm_group' needs to be implemented"
        )

    def remove_sgtk_parms(self, node):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        :return: Whether Shotgun parameters were removed from node.
        :rtype: bool
        """
        use_sgtk = node.parm(self.USE_SGTK)
        if not use_sgtk:
            return False
        use_sgtk.set(False)
        self._enable_sgtk(node, False)
        parameter_group = self._get_parameter_group(node)
        self._remove_sgtk_items_from_parm_group(parameter_group)
        node.setParmTemplateGroup(parameter_group.build())
        return True

    def _restore_sgtk_parms(self, node):
        """
        Restore any removed sgtk parameters onto the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        """
        raise NotImplementedError("'_restore_sgtk_parms' needs to be implemented")

    def restore_sgtk_parms(self, node):
        """
        Restore any removed sgtk parameters onto the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        """
        sgtk_identifier = node.parm(self.SGTK_IDENTIFIER)
        use_sgtk = node.parm(self.USE_SGTK)
        if sgtk_identifier and not use_sgtk:
            self._restore_sgtk_parms(node)

    ###########################################################################
    # houdini callback overrides
    ###########################################################################

    def on_created(self, node=None):
        """
        Method to run on houdini's OnCreated callback.

        :param node: A :class:`hou.Node` instance.
        """
        self.add_sgtk_parms(node)

    def on_deleted(self, node=None):
        """
        Method to run on houdini's OnDeleted callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def on_input_changed(self, node=None):
        """
        Method to run on houdini's OnInputChanged callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def on_loaded(self, node=None):
        """
        Method to run on houdini's OnLoaded callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def on_name_changed(self, node=None):
        """
        Method to run on houdini's OnNameChanged callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def on_updated(self, node=None):
        """
        Method to run on houdini's OnUpdated callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def before_first_create(self, node=None):
        """
        Method to run on houdini's BeforeFirstCreated callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def after_last_delete(self, node=None):
        """
        Method to run on houdini's AfterLastDelete callback.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    ###########################################################################
    # UI customisation
    ###########################################################################

    def _get_parameter_group(self, node):
        """
        Get the given node's parameter group.

        :param node: A :class:`hou.Node` instance.

        :rtype: :class:`ParmGroup` or None.
        """
        group = None
        if node:
            tk_houdini = self.parent.import_module("tk_houdini")
            group = tk_houdini.utils.wrap_node_parameter_group(node)
        return group

    def _set_up_parms(self, node):
        """
        Set up the given node's parameters.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        """
        Here is where you define where the sgtk folder is to be placed, but also
        any other parameters that you wish to add to the node.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        :param sgtk_folder: A :class:`hou.ParmFolderTemplate` containing sgtk
            parameters.
        """
        raise NotImplementedError(
            "'_customise_parameter_group' needs to be implemented"
        )

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        return []

    def _create_sgtk_folder(self, node, use_sgtk_default=True, hou=None):
        """
        Create the sgtk folder template.

        This contains the common parameters used by all node handlers.

        :param node: A :class:`hou.Node` instance.
        :param bool use_sgtk_default: Whether the "Use Shotgun" checkbox is to be
            checked by default.
        :param hou: The houdini module. We have to lazy load the houdini python
            module here, but not in the hooks, so use hook's imports and pass it
            for efficiency.
        """
        if not hou:
            import hou
        sgtk_templates = []

        use_sgtk = hou.ToggleParmTemplate(
            self.USE_SGTK,
            "Use Shotgun",
            default_value=use_sgtk_default,
            script_callback=self.generate_callback_script_str("enable_sgtk"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_templates.append(use_sgtk)

        sgtk_templates.extend(self._create_sgtk_parms(node))

        all_versions = hou.StringParmTemplate(
            self.SGTK_ALL_VERSIONS, "All Versions", 1, is_hidden=True
        )
        sgtk_templates.append(all_versions)

        version = hou.MenuParmTemplate(
            self.SGTK_VERSION,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str(
                "populate_versions"
            ),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str(
                "refresh_file_path_from_version"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        version.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        version.setJoinWithNext(True)
        sgtk_templates.append(version)

        refresh_button = hou.ButtonParmTemplate(
            self.SGTK_REFRESH_VERSIONS,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str(
                "refresh_file_path_from_version"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        refresh_button.setConditional(
            hou.parmCondType.DisableWhen, '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        refresh_button.setJoinWithNext(True)
        sgtk_templates.append(refresh_button)

        resolved_version = hou.StringParmTemplate(
            self.SGTK_RESOLVED_VERSION, "Resolved Version", 1, default_value=("1",)
        )
        resolved_version.setConditional(
            hou.parmCondType.DisableWhen, "{ sgtk_version != -1 }"
        )
        sgtk_templates.append(resolved_version)

        engine_version = (
            self.parent.version if self.parent.version != "Undefined" else "DEV"
        )
        sgtk_folder = hou.FolderParmTemplate(
            self.SGTK_FOLDER,
            "SGTK (ver: {})".format(engine_version),
            parm_templates=sgtk_templates,
            folder_type=hou.folderType.Simple,
        )
        return sgtk_folder

    def _set_up_node(self, node, parameter_group, hou=None):
        """
        Set up a node for use with shotgun pipeline.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: A :class:`ParmGroup` instance.
        :param hou: The houdini module. We have to lazy load the houdini python
            module here, but not in the hooks, so use hook's imports and pass it
            for efficiency.
        """
        if not hou:
            import hou
        self._set_up_parms(node)
        sgtk_folder = self._create_sgtk_folder(node)
        if self.SGTK_IDENTIFIER not in parameter_group:
            sgtk_identifier = hou.ToggleParmTemplate(
                self.SGTK_IDENTIFIER, "SGTK", default_value=True, is_hidden=True
            )
            parameter_group.append_template(sgtk_identifier)
        self._customise_parameter_group(node, parameter_group, sgtk_folder)
        node.setParmTemplateGroup(parameter_group.build())

    def add_sgtk_parms(self, node):
        """
        Add sgtk parameters to the given node.

        :param node: A :class:`hou.Node` instance.
        """
        parameter_group = self._get_parameter_group(node)
        if parameter_group:
            self._set_up_node(node, parameter_group)

    ###########################################################################
    # UI Callbacks
    ###########################################################################

    def activate_sgtk(self, node):
        """
        Activate Shotgun parameters and callbacks if not already.

        Commonly used by ``tk-multi-loader2`` hooks.

        :param node: A :class:`hou.Node` instance.
        """
        use_sgtk = node.parm(self.USE_SGTK)
        if not use_sgtk.eval():
            use_sgtk.set(True)
            self._enable_sgtk(node, True)

    def _enable_sgtk(self, node, sgtk_enabled):
        """
        Enable/disable the sgtk parameters.

        :param node: A :class:`hou.Node` instance.
        :param bool sgtk_enabled: The state to set the parameters to.
        """
        pass

    def enable_sgtk(self, kwargs):
        """
        Callback to enable/disable the sgtk parameters.
        """
        node = kwargs["node"]
        use_sgtk = node.parm(self.USE_SGTK)
        value = use_sgtk.eval()
        self._enable_sgtk(node, value)
        if value:
            self.refresh_file_path(kwargs)

    def _get_all_versions(self, node):
        """
        Retrieve all the versions stored on the node.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(int)
        """
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        all_versions_str = sgtk_all_versions.evalAsString()
        all_versions = filter(None, all_versions_str.split(","))
        all_versions = map(int, all_versions)
        return list(all_versions)

    def _populate_versions(self, node):
        """
        Get the versions in a format to populate the "sgtk_all_versions"
        parameter on the node.

        :param node: A :class:`hou.Node` instance.

        :return: list(str), for example '["1", "1", "2", "2", "3", "3"]'
        """
        all_versions = self._get_all_versions(node)
        versions = map(str, all_versions)
        versions.extend(self.VERSION_POLICIES)
        return list(itertools.chain(*zip(versions, versions)))

    def populate_versions(self, kwargs):
        """
        Callback to get the versions in a format to populate the "sgtk_all_versions"
        parameter on the node.

        :return: list(str), for example '["1", "1", "2", "2", "3", "3"]'
        """
        node = kwargs["node"]
        return self._populate_versions(node)

    def _refresh_file_path(self, node):
        """
        Refresh the file paths generated by the node handler.

        :param node: A :class:`hou.Node` instance.
        """
        pass

    def refresh_file_path(self, kwargs):
        """
        Callback to refresh the file paths generated by the node handler.
        """
        node = kwargs["node"]
        self._refresh_file_path(node)

    def refresh_file_path_from_version(self, kwargs):
        """
        Callback to refresh the file paths generated by the node handler when the
        version is updated.
        """
        node = kwargs["node"]
        self._refresh_file_path(node)
