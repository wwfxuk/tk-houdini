import copy
import json

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ImportNodeHandler(HookBaseClass):

    INPUT_PARM = "file"

    LATEST_POLICY = "<LATEST>"
    LATEST_COMPLETE_POLICY = "<LATEST COMPLETE>"

    VERSION_POLICIES = [LATEST_POLICY, LATEST_COMPLETE_POLICY]

    SGTK_NAME = "sgtk_name"
    SGTK_ID = "sgtk_id"
    SGTK_BROWSE = "sgtk_browse"
    SGTK_PUBLISH_DATA = "sgtk_publish_data"
    SGTK_LAST_USED = "sgtk_last_used"

    VALID_FILE_TYPES = "valid_file_types"

    ACCEPTS_MULTI_SELECTION = False

    @property
    def valid_file_types(self):
        self.extra_args.get(self.VALID_FILE_TYPES, [])

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        index = parameter_group.index_of_template(self.INPUT_PARM)
        parameter_group.insert_template(index, sgtk_folder)

    def _setup_parms(self, node):
        input_parm = node.parm(self.INPUT_PARM)
        input_parm.lock(True)

    def _set_up_node(self, node, parameter_group):
        if not self.SGTK_PUBLISH_DATA in parameter_group:
            sgtk_publish_data = hou.StringParmTemplate(
                self.SGTK_PUBLISH_DATA,
                "publish data",
                1,
                is_hidden=True
            )
            parameter_group.append_template(sgtk_publish_data)
        if not self.SGTK_LAST_USED in parameter_group:
            sgtk_last_used = hou.ToggleParmTemplate(
                self.SGTK_LAST_USED,
                "shotgun last used",
                default_value=True,
                is_hidden=True
            )
            parameter_group.append_template(sgtk_last_used)
        super(ImportNodeHandler, self)._set_up_node(node, parameter_group, hou=hou)

    def _create_sgtk_parms(self, node):
        templates = super(ImportNodeHandler, self)._create_sgtk_parms(node, hou=hou)

        sgtk_name = hou.StringParmTemplate(
            self.SGTK_NAME,
            "Name",
            1
        )
        sgtk_name.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != -1 }")
        sgtk_name.setJoinWithNext(True)
        templates.append(sgtk_name)

        sgtk_id = hou.StringParmTemplate(
            self.SGTK_ID,
            "Id",
            1
        )
        sgtk_id.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != -1 }")
        sgtk_id.setJoinWithNext(True)
        templates.append(sgtk_id)

        sgtk_browse = hou.ButtonParmTemplate(
            self.SGTK_BROWSE,
            "Browse",
            script_callback=self.generate_callback_script_str("load_from_shotgun"),
            script_callback_language=hou.scriptLanguage.Python
        )
        sgtk_browse.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        templates.append(sgtk_browse)

        return templates

    def _create_sgtk_folder(self, node):
        return super(ImportNodeHandler, self)._create_sgtk_folder(node, hou=hou)

    #############################################################################################
    # UI Callbacks
    #############################################################################################
    
    def _enable_sgtk(self, node, sgtk_enabled):
        output_parm = node.parm(self.INPUT_PARM)
        output_parm.lock(sgtk_enabled)

    def enable_sgtk(self, kwargs):
        super(ImportNodeHandler, self).enable_sgtk(kwargs)
        node = kwargs["node"]
        use_sgtk = node.parm(self.USE_SGTK)
        value = use_sgtk.eval()
        sgtk_last_used = node.parm(self.SGTK_LAST_USED)
        sgtk_last_used.set(value)

    def _resolve_version(self, all_versions_and_statuses, current):
        self.parent.log_debug("ALL VERSIONS: {!r}".format(all_versions_and_statuses))
        self.parent.log_debug("CURRENT: {}".format(current))
        all_versions = self._extract_versions(all_versions_and_statuses)
        if current == self.LATEST_POLICY:
            return max(all_versions)
        elif current == self.LATEST_COMPLETE_POLICY:
            versions_and_statuses = [(x["version"], x["status"]) for x in all_versions_and_statuses]
            all_cmpt = filter(
                    lambda item: item[1] == "cmpt",
                    versions_and_statuses
                )
            if all_cmpt:
                return max(all_cmpt)[0]
            return max(all_versions)
        else:
            resolved = int(current)
            if resolved not in all_versions:
                resolved = max(all_versions)
            return resolved
        
    def _refresh_file_path_from_publish_data(self, node, publish_data):
        name = publish_data.get("name") or publish_data.get("code", "")
        sgtk_name = node.parm(self.SGTK_NAME)
        sgtk_name.set(name)

        all_versions_and_statuses = self._resolve_all_versions_and_statuses_from_publish_data(
            publish_data
        )
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        sgtk_all_versions.set(json.dumps(all_versions_and_statuses))

        sgtk_version = node.parm(self.SGTK_VERSION)
        current = sgtk_version.evalAsString()
        resolved_version = self._resolve_version(all_versions_and_statuses, current)

        sgtk_resolved_version = node.parm(self.SGTK_RESOLVED_VERSION)
        sgtk_resolved_version.set(str(resolved_version))

        sg = self.parent.shotgun
        filters = self._get_search_filters_from_publish_data(publish_data)
        filters.append(["version_number", "is", resolved_version])
        result = sg.find_one(
            "PublishedFile",
            filters,
            ["id", "path"]
        ) or {}

        id_ = str(result.get("id", ""))
        sgtk_id = node.parm(self.SGTK_ID)
        sgtk_id.set(id_)

        if not result:
            path = "Failed to get publish entity"
        else:
            path = self._get_path_from_sg_data(result)

        input_parm = node.parm(self.INPUT_PARM)
        input_parm.lock(False)
        input_parm.set(path)
        input_parm.lock(True)

    def _refresh_file_path(self, node, update_version=True):
        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        publish_data_str = sgtk_publish_data.evalAsString()
        if not publish_data_str:
            return
        self.parent.log_debug("{!r}\n\t{}".format(publish_data_str, type(publish_data_str).__name__))
        publish_data = json.loads(publish_data_str)
        
        self._refresh_file_path_from_publish_data(node, publish_data)

    @staticmethod
    def _get_path_from_sg_data(data):
        """
        Get the file path from the publish data.

        :param dict data: The publish data.

        :returns: :class:`str`
        """
        none_found_msg = "No path found in shotgun"
        path = data["path"]
        linkType = path.get("link_type")
        if linkType == "web":
            url = path.get("url")
            if not url:
                return none_found_msg
            elif url.startswith("file://"):
                    return url[7:]
        elif linkType == "upload":
            url = path.get("url")
            if not url:
                return none_found_msg
            return "Importing from URL is currently unsupported"
        elif linkType == "local":
            return path.get("local_path")
        return none_found_msg

    @staticmethod
    def _get_search_filters_from_publish_data(publish_data):
        publish_file_type = publish_data.get("published_file_type", {})
        entity = publish_data.get("entity", {})
        project = publish_data.get("project", {})
        name = publish_data.get("name") or publish_data.get("code", "")
        return [
            ["published_file_type", "is", publish_file_type],
            ["entity", "is", entity],
            ["project", "is", project],
            ["name", "is", name]
        ]

    def _resolve_all_versions_and_statuses_from_publish_data(self, publish_data):
        filters = self._get_search_filters_from_publish_data(publish_data)
        sg = self.parent.shotgun
        results = sg.find(
            "PublishedFile",
            filters,
            ["version_number", "sg_status_list"]
        )
        versions_and_statuses = []

        for result in sorted(results, key=lambda item: item["version_number"]):
            if result["sg_status_list"] == "decl":
                continue
            versions_and_statuses.append(
                {
                    "version": result["version_number"],
                    "status": result["sg_status_list"]
                }
            )
        self.parent.log_debug("{!r}\n\t{}".format(versions_and_statuses, type(versions_and_statuses).__name__))
        return versions_and_statuses

    def _update_publish_data_parm(self, node, publish_data, version_policy):
        self.parent.log_debug("VERSION_POLICY: {}".format(version_policy))
        publish_data["version_policy"] = version_policy
        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        sgtk_publish_data.set(json.dumps(publish_data))
        
        sgtk_version = node.parm(self.SGTK_VERSION)
        all_versions = self._extract_versions(
            self._resolve_all_versions_and_statuses_from_publish_data(publish_data)
        )
        menu_items = all_versions + self.VERSION_POLICIES
        self.parent.log_debug("MENU_ITEMS: {!r}".format(menu_items))
        if version_policy in self.VERSION_POLICIES:
            index = menu_items.index(version_policy)
        else:
            index = menu_items.index(publish_data["version_number"])
        sgtk_version.set(index)

    def populate_node_from_publish_data(self, node, publish_data, version_policy=None):
        if publish_data:
            if self.ACCEPTS_MULTI_SELECTION and not isinstance(publish_data, list):
                publish_data = [publish_data]
            elif not self.ACCEPTS_MULTI_SELECTION and isinstance(publish_data, list):
                publish_data = publish_data[0]
        self._update_publish_data_parm(node, publish_data, version_policy)
        self._refresh_file_path(node)

    def _load_from_shotgun(self, node):
        tk_multi_loader_app = self.parent.apps.get("tk-multi-loader2")
        if not tk_multi_loader_app:
            self.parent.log_error("'tk-multi-loader2' not loaded")
            return
        tk_multi_loader = tk_multi_loader_app.import_module("tk_multi_loader")

        utils = self.parent.import_module("tk_houdini").utils
        action_manager = utils.HoudiniActionManager(self, node)
        
        widget = tk_multi_loader.dialog.AppDialog(
            action_manager,
            parent=hou.ui.mainQtWindow()
        )
        self.parent._apply_external_stylesheet(self.parent, widget)
        widget.setWindowFlags(widget.windowFlags() | sgtk.platform.qt.QtCore.Qt.Window)
        widget.setWindowModality(sgtk.platform.qt.QtCore.Qt.WindowModal)
        action_manager.on_action_triggered.connect(widget.close)
        widget.show()

    def load_from_shotgun(self, kwargs):
        node = kwargs["node"]
        self._load_from_shotgun(node)

    def _get_all_versions_and_statuses(self, node, parm_name):
        sgtk_all_versions = node.parm(parm_name)
        all_versions_json = sgtk_all_versions.evalAsString() or "[]"
        all_versions_and_statuses = json.loads(all_versions_json)
        return all_versions_and_statuses

    @staticmethod
    def _extract_versions(versions_and_statuses):
        return [x["version"] for x in versions_and_statuses]

    def _get_all_versions(self, node, parm_name):
        return self._extract_versions(self._get_all_versions_and_statuses(node, parm_name))

    def _retrieve_publish_data(self, node):
        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        default = "[]" if self.ACCEPTS_MULTI_SELECTION else "{}"
        publish_data_str = sgtk_publish_data.evalAsString() or default
        publish_data = json.loads(publish_data_str)
        self.parent.log_debug("PUBLISH_DATA: {}".format(json.dumps(publish_data, indent=4)))
        return publish_data

    def refresh_file_path_from_version(self, kwargs):
        node = kwargs["node"]
        publish_data = self._retrieve_publish_data(node)
        sgtk_version = node.parm(self.SGTK_VERSION)
        version = sgtk_version.evalAsString()
        version_policy = version if version in self.VERSION_POLICIES else None
        self._update_publish_data_parm(node, publish_data, version_policy)
        super(ImportNodeHandler, self).refresh_file_path_from_version(kwargs)

    #############################################################################################
    # Utilities
    #############################################################################################
    
    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)

    def _restore_sgtk_parms(self, node):
        input_parm = node.parm(self.INPUT_PARM)
        original_file_path = input_parm.unexpandedString()

        publish_data = self._retrieve_publish_data(node)
        self.add_sgtk_parms(node)
        all_versions_and_statuses = self._resolve_all_versions_and_statuses_from_publish_data(
            publish_data
        )
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        sgtk_all_versions.set(json.dumps(all_versions_and_statuses))
        self.populate_node_from_publish_data(node, publish_data, publish_data["version_policy"])

        sgtk_last_used = node.parm(self.SGTK_LAST_USED)
        if not sgtk_last_used.eval():
            use_sgtk = node.parm(self.USE_SGTK)
            use_sgtk.set(False)
            self._enable_sgtk(node, False)
            input_parm.set(original_file_path)

    def get_input_paths(self, node):
        if not node.parm(self.USE_SGTK).eval():
            return []

        input_paths = []

        main_input = node.parm(self.INPUT_PARM)
        path = main_input.unexpandedString()
        input_paths.append(path)

        return input_paths