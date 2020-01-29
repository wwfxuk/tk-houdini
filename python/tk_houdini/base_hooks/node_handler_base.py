import itertools

import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class NodeHandlerBase(HookBaseClass):

    NODE_TYPE = None

    VERSION_POLICIES = []

    SGTK_ALL_VERSIONS = "sgtk_all_versions"
    SGTK_VERSION = "sgtk_version"
    SGTK_REFRESH_VERSIONS = "sgtk_refresh_versions"
    SGTK_RESOLVED_VERSION = "sgtk_resolved_version"
    SGTK_FOLDER = "sgtk_folder"
    USE_SGTK = "use_sgtk"

    def __new__(cls, *args, **kwargs):
        if cls.NODE_TYPE:
            if hasattr(cls, "_work_template"):
                return super(NodeHandlerBase, cls).__new__(cls, *args, **kwargs)
            engine = sgtk.platform.current_engine()
            node_handlers = engine.get_setting("node_handlers")
            for handler in node_handlers:
                if handler["node_type"] == cls.NODE_TYPE:
                    work_template = engine.get_template_by_name(handler["work_template"])
                    setattr(cls, "_work_template", work_template)
                    publish_template = engine.get_template_by_name(handler["publish_template"])
                    setattr(cls, "_publish_template", publish_template)
                    setattr(cls, "extra_args", handler["extra_args"])
        return super(NodeHandlerBase, cls).__new__(cls, *args, **kwargs)

    @staticmethod
    def generate_callback_script_str(method_name):
        callback_str = (
            "__import__('sgtk').platform.current_engine().node_handler(kwargs['node'])"
            ".{method}(kwargs)"
        ).format(method=method_name)
        return callback_str

    def get_work_template(self, node):
        return self._work_template

    def get_publish_template(self, node):
        return self._publish_template
        
    def _get_template(self, template_name):
        template_name = self.extra_args.get(template_name)
        if not template_name:
            raise sgtk.TankError("No template name defined")
        template = self.parent.get_template_by_name(template_name)
        if not template:
            raise sgtk.TankError("Can't find template")
        return template

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        raise NotImplementedError("'_remove_sgtk_items_from_parm_group' needs to be implemented")

    def remove_sgtk_parms(self, node):
        use_sgtk = node.parm(self.USE_SGTK)
        if not use_sgtk:
            return False
        use_sgtk.set(False)
        self._enable_sgtk(node, False)
        tk_houdini = self.parent.import_module("tk_houdini")
        utils = tk_houdini.utils
        parameter_group = utils.wrap_node_parameter_group(node)
        self._remove_sgtk_items_from_parm_group(parameter_group)
        node.setParmTemplateGroup(parameter_group.build())
        return True

    def _restore_sgtk_parms(self, node):
        raise NotImplementedError("'_restore_sgtk_parms' needs to be implemented")

    def restore_sgtk_parms(self, node):
        use_sgtk = node.parm(self.USE_SGTK)
        if use_sgtk:
            return
        self._restore_sgtk_parms(node)

    #############################################################################################
    # houdini callback overrides
    #############################################################################################
    
    def on_created(self, node=None):
        self.add_sgtk_parms(node)

    def on_deleted(self, node=None):
        pass

    def on_input_changed(self, node=None):
        pass

    def on_loaded(self, node=None):
        pass

    def on_name_changed(self, node=None):
        pass

    def on_updated(self, node=None):
        pass

    def before_first_create(self, node=None):
        pass

    def after_last_delete(self, node=None):
        pass

    #############################################################################################
    # UI customisation
    #############################################################################################
        
    def _get_parameter_group(self, node):
        if not node:
            return
        tk_houdini = self.parent.import_module("tk_houdini")
        utils = tk_houdini.utils
        return utils.wrap_node_parameter_group(node)

    def _set_up_parms(self, node):
        pass

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        raise NotImplementedError("'_customise_parameter_group' needs to be implemented")

    def _create_sgtk_parms(self, node, hou=None):
        if not hou:
            import hou
        templates = []
        use_sgtk = hou.ToggleParmTemplate(
            self.USE_SGTK,
            "Use Shotgun",
            default_value=True,
            script_callback=self.generate_callback_script_str("enable_sgtk"),
            script_callback_language=hou.scriptLanguage.Python
        )
        templates.append(use_sgtk)
        return templates
    
    def _create_sgtk_folder(self, node, hou=None):
        if not hou:
            import hou
        sgtk_templates = self._create_sgtk_parms(node)
        
        all_versions = hou.StringParmTemplate(
            self.SGTK_ALL_VERSIONS,
            "All Versions",
            1,
            is_hidden=True
        )
        sgtk_templates.append(all_versions)

        version = hou.MenuParmTemplate(
            self.SGTK_VERSION,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str("populate_versions"),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str("refresh_file_path_from_version"),
            script_callback_language=hou.scriptLanguage.Python
        )
        version.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        version.setJoinWithNext(True)
        sgtk_templates.append(version)

        refresh_button = hou.ButtonParmTemplate(
            self.SGTK_REFRESH_VERSIONS,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str("refresh_file_path_from_version"),
            script_callback_language=hou.scriptLanguage.Python
        )
        refresh_button.setConditional(
            hou.parmCondType.DisableWhen,
            '{ use_sgtk != 1 } { sgtk_element == "" }'
        )
        refresh_button.setJoinWithNext(True)
        sgtk_templates.append(refresh_button)

        resolved_version = hou.StringParmTemplate(
            self.SGTK_RESOLVED_VERSION,
            "Resolved Version",
            1,
            default_value=("1",)
        )
        resolved_version.setConditional(hou.parmCondType.DisableWhen, "{ sgtk_version != -1 }")
        sgtk_templates.append(resolved_version)
        
        sgtk_folder = hou.FolderParmTemplate(
            self.SGTK_FOLDER,
            "SGTK",
            parm_templates=sgtk_templates,
            folder_type=hou.folderType.Simple
        )
        return sgtk_folder

    def _set_up_node(self, node, parameter_group):
        self._set_up_parms(node)
        sgtk_folder = self._create_sgtk_folder(node)
        self._customise_parameter_group(node, parameter_group, sgtk_folder)
        node.setParmTemplateGroup(parameter_group.build())

    def add_sgtk_parms(self, node):
        parameter_group = self._get_parameter_group(node)
        if not parameter_group:
            return
        self._set_up_node(node, parameter_group)

    #############################################################################################
    # UI Callbacks
    #############################################################################################
    
    def _enable_sgtk(self, node, sgtk_enabled):
        pass

    def enable_sgtk(self, kwargs):
        node = kwargs["node"]
        use_sgtk = node.parm(self.USE_SGTK)
        value = use_sgtk.eval()
        self._enable_sgtk(node, value)
        if value:
            self.refresh_file_path(kwargs)

    def _get_all_versions(self, node):
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        all_versions_str = sgtk_all_versions.evalAsString()
        all_versions = filter(None, all_versions_str.split(","))
        all_versions = map(int, all_versions)
        return all_versions

    def _populate_versions(self, node):
        all_versions = self._get_all_versions(node)
        versions = map(str, all_versions)
        versions.extend(self.VERSION_POLICIES)
        return list(itertools.chain(*zip(versions, versions)))

    def populate_versions(self, kwargs):
        node = kwargs["node"]
        return self._populate_versions(node)

    def _refresh_file_path(self, node, update_version=True):
        pass

    def refresh_file_path(self, kwargs):
        node = kwargs["node"]
        self._refresh_file_path(node)

    def refresh_file_path_from_version(self, kwargs):
        node = kwargs["node"]
        sgtk_version = node.parm(self.SGTK_VERSION)
        update_version = sgtk_version.evalAsString() in self.VERSION_POLICIES
        self._refresh_file_path(node, update_version=update_version)
