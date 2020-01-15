import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class NodeHandlerBase(HookBaseClass):

    NODE_TYPE = None

    OUTPUT_PARM = None

    OUTPUT_PARM_EXPR = 'chs("./sgtk_output")'
    SGTK_OUTPUT = "sgtk_output"
    SGTK_ELEMENT = "sgtk_element"
    SGTK_LOCATION = "sgtk_location"
    SGTK_VARIATION = "sgtk_variation"
    SGTK_ALL_VERSIONS = "sgtk_all_versions"
    SGTK_VERSION = "sgtk_version"
    SGTK_REFRESH_VERSIONS = "sgtk_refresh_versions"
    SGTK_RESOLVED_VERSION = "sgtk_resolved_version"
    SGTK_FOLDER = "sgtk_folder"
    USE_SGTK = "use_sgtk"
    NEXT_VERSION_STR = "<NEXT>"

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
        work_template_name = self.extra_args.get(template_name)
        if not work_template_name:
            raise sgtk.TankError("No workfile template name defined")
        work_template = self.parent.get_template_by_name(work_template_name)
        if not work_template:
            raise sgtk.TankError("Can't find work template")
        return work_template

    #############################################################################################
    # Utilities
    #############################################################################################

    def remove_sgtk_parms(self, node):
        pass

    def populate_sgtk_parms(self, node, use_next_version=True):
        pass

    #############################################################################################
    # houdini callback overrides
    #############################################################################################
    
    def on_created(self, node=None):
        pass

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
