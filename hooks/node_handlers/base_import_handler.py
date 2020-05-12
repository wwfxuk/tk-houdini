"""Base Hook for other Houdini import node handlers.

These include:

- ``alembic_import_handler``
- ``file_handler``
- ``image_handler``

"""
import datetime
import json
import re

import sgtk

import hou

HookBaseClass = sgtk.get_hook_baseclass()


class ImportNodeHandler(HookBaseClass):
    """
    Base class for all import node handlers.
    """
    NODE_TYPE = "alembic"
    NODE_CATEGORY = "Sop"

    INPUT_PARM = None

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
        """
        List of all the valid file types for this node handler.

        :rtype: list(str)
        """
        return self.extra_args.get(self.VALID_FILE_TYPES, [])

    @staticmethod
    def _validate_publish_data(publish_data):
        """
        Validate the publish data.

        Must include:
        - entity
        - project
        - name
        - published_file_type

        :rtype: bool
        """
        return all(
            [
                "entity" in publish_data,
                "project" in publish_data,
                "name" in publish_data,
                "published_file_type" in publish_data,
            ]
        )

    #############################################################################################
    # UI customisation
    #############################################################################################

    def _customise_parameter_group(self, node, parameter_group, sgtk_folder):
        """
        Here is where you define where the sgtk folder is to be placed, but also
        any other parameters that you wish to add to the node.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: The node's :class:`ParmGroup`.
        :param sgtk_folder: A :class:`hou.ParmFolderTemplate` containing sgtk
            parameters.
        """
        index = parameter_group.index_of_template(self.INPUT_PARM)
        parameter_group.insert_template(index, sgtk_folder)

    def _set_up_node(self, node, parameter_group):
        """
        Set up a node for use with shotgun pipeline.

        :param node: A :class:`hou.Node` instance.
        :param parameter_group: A :class:`ParmGroup` instance.
        """
        if self.SGTK_PUBLISH_DATA not in parameter_group:
            sgtk_publish_data = hou.StringParmTemplate(
                self.SGTK_PUBLISH_DATA, "publish data", 1, is_hidden=True
            )
            parameter_group.append_template(sgtk_publish_data)
        if self.SGTK_LAST_USED not in parameter_group:
            sgtk_last_used = hou.ToggleParmTemplate(
                self.SGTK_LAST_USED,
                "shotgun last used",
                default_value=False,
                is_hidden=True,
            )
            parameter_group.append_template(sgtk_last_used)
        super(ImportNodeHandler, self)._set_up_node(node, parameter_group, hou=hou)

    def _create_sgtk_parms(self, node):
        """
        Create the parameters that are going to live within the sgtk folder.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(:class:`hou.ParmTemplate`)
        """
        templates = []

        sgtk_name = hou.StringParmTemplate(self.SGTK_NAME, "Name", 1)
        sgtk_name.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != -1 }")
        sgtk_name.setJoinWithNext(True)
        templates.append(sgtk_name)

        sgtk_id = hou.StringParmTemplate(self.SGTK_ID, "Id", 1)
        sgtk_id.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != -1 }")
        sgtk_id.setJoinWithNext(True)
        templates.append(sgtk_id)

        sgtk_browse = hou.ButtonParmTemplate(
            self.SGTK_BROWSE,
            "Browse",
            script_callback=self.generate_callback_script_str("load_from_shotgun"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        sgtk_browse.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        templates.append(sgtk_browse)

        return templates

    def _create_sgtk_folder(self, node):
        """
        Create the sgtk folder template.

        This contains the common parameters used by all node handlers.

        :param node: A :class:`hou.Node` instance.
        :param bool use_sgtk_default: Whether the "Use Shotgun" checkbox is to be
            checked by default.
        """
        return super(ImportNodeHandler, self)._create_sgtk_folder(
            node, use_sgtk_default=False, hou=hou
        )

    #############################################################################################
    # UI Callbacks
    #############################################################################################

    def _enable_sgtk(self, node, sgtk_enabled):
        """
        Enable/disable the sgtk parameters.

        :param node: A :class:`hou.Node` instance.
        :param bool sgtk_enabled: The state to set the parameters to.
        """
        output_parm = node.parm(self.INPUT_PARM)
        output_parm.lock(sgtk_enabled)

    def enable_sgtk(self, kwargs):
        """
        Callback to enable/disable the sgtk parameters.
        """
        super(ImportNodeHandler, self).enable_sgtk(kwargs)
        node = kwargs["node"]
        use_sgtk = node.parm(self.USE_SGTK)
        value = use_sgtk.eval()
        sgtk_last_used = node.parm(self.SGTK_LAST_USED)
        sgtk_last_used.set(value)

    def _resolve_version(self, all_versions_and_statuses, current):
        """
        From a given string, resolve the current version.
        Either a specified version or the next version in the sequence.

        :param list(dict) all_versions_and_statuses: All the existing versions and
            their pipeline status.
        :param str current: The currently selected version option.

        :rtype: int
        """
        self.parent.logger.debug("ALL VERSIONS: %r", all_versions_and_statuses)
        self.parent.logger.debug("CURRENT: %r", current)

        all_versions = self._extract_versions(all_versions_and_statuses) or [1]

        if current == self.LATEST_COMPLETE_POLICY:
            all_cmpt = [
                item["version"]
                for item in all_versions_and_statuses
                if item["status"] == "cmpt"
            ]
            resolved = max(all_cmpt or all_versions)

        elif current == self.LATEST_POLICY:
            resolved = max(all_versions)

        else:
            resolved = int(current)
            if resolved not in all_versions:
                self.parent.logger.warn("Current version is not published: %r", current)
                resolved = max(all_versions)
                self.parent.logger.warn("Switching to use version: %r", resolved)

        return resolved

    def _refresh_file_path_from_publish_data(self, node, publish_data):
        """
        Refresh the file path from the given publish data.

        :param node: A :class:`hou.Node` instance.
        :param dict publish_data: The publush data to populate from.
        """
        if not self._validate_publish_data(publish_data):
            return
        name = publish_data.get("name") or publish_data.get("code", "")
        sgtk_name = node.parm(self.SGTK_NAME)
        sgtk_name.set(name)

        all_versions_and_statuses = self._resolve_all_versions_statuses(publish_data)
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
        result = sg.find_one("PublishedFile", filters, ["id", "path"]) or {}

        id_ = str(result.get("id", ""))
        sgtk_id = node.parm(self.SGTK_ID)
        sgtk_id.set(id_)

        if not result:
            path = "Failed to get publish entity"
        else:
            path = self._get_path_from_sg_data(result)
            path = self._convert_path_to_houdini_seq(path)

        input_parm = node.parm(self.INPUT_PARM)
        input_parm.lock(False)
        input_parm.set(path)
        input_parm.lock(True)

    def _convert_path_to_houdini_seq(self, path):
        """
        Convert incoming sequence paths into houdini formatted ones. ($F4)

        :param str path: The incoming file path.

        :returns: A houdini-formatted sequence path.
        """

        def repl(match):
            """Replace all sequence matches with the format ``.$F[0-9].``.

            :param match: Result from a matching substring.
            :type match: re.MatchObject
            :return: Houdini friendly file sequence format.
            :rtype: str
            """
            parts = match.groupdict()
            if parts["symbols"]:
                pad_amount = len(parts["symbols"])
            else:
                pad_amount = parts["padding"]
            return ".$F{}.".format(pad_amount)

        return re.sub(
            r"\.(?P<symbols>[@#]+)\.|\.([%0$F]{2}(?P<padding>[0-9])d?)\.", repl, path
        )

    def _refresh_file_path(self, node):
        """
        Refresh the file paths generated by the node handler.

        :param node: A :class:`hou.Node` instance.
        """
        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        publish_data_str = sgtk_publish_data.evalAsString()
        if publish_data_str:
            publish_data = json.loads(self._escape_publish_data(publish_data_str))
            self._refresh_file_path_from_publish_data(node, publish_data)

    @staticmethod
    def _escape_publish_data(publish_data_str):
        """
        Utility to escape publish data strings for json loading.

        :param str publish_data_str: The serialised publish data.

        :returns: A string that json can deal with.
        """
        try:
            return publish_data_str.encode("unicode_escape")
        except UnicodeDecodeError:
            return publish_data_str.encode("string_escape")

    @staticmethod
    def _get_path_from_sg_data(data):
        """
        Get the file path from the publish data.

        :param dict data: The publish data.

        :returns: :class:`str`
        """
        result = "No path found in shotgun"
        path = data["path"]
        link_type = path.get("link_type")

        if link_type == "web":
            url = path.get("url")
            if url and url.startswith("file://"):
                result = url[7:]

        elif link_type == "upload":
            url = path.get("url")
            if url:
                result = "Importing from URL is currently unsupported"

        elif link_type == "local":
            result = path.get("local_path")

        return result

    @staticmethod
    def _get_search_filters_from_publish_data(publish_data):
        """
        Construct search filters from the publish data.

        :param dict publish_data: The publish data to use for the query.

        :rtype: list
        """
        publish_file_type = publish_data.get("published_file_type", {})
        entity = publish_data.get("entity", {})
        project = publish_data.get("project", {})
        name = publish_data.get("name") or publish_data.get("code", "")
        return [
            ["published_file_type", "is", publish_file_type],
            ["entity", "is", entity],
            ["project", "is", project],
            ["name", "is", name],
        ]

    def _resolve_all_versions_statuses(self, publish_data):
        """
        Get all the available versions and their pipeline statuses from the given
        entity publish data.

        :param dict publish_data: The publish data to use for the query.

        :returns: A list(:class:`dict`) of versions and relating statuses.
        """
        valid_publish_data = self._validate_publish_data(publish_data)
        if not valid_publish_data:
            return []
        filters = self._get_search_filters_from_publish_data(publish_data)
        sg = self.parent.shotgun
        results = sg.find(
            "PublishedFile", filters, ["version_number", "sg_status_list"]
        )
        versions_and_statuses = []

        for result in sorted(results, key=lambda item: item["version_number"]):
            if result["sg_status_list"] == "decl":
                continue
            versions_and_statuses.append(
                {
                    "version": result["version_number"],
                    "status": result["sg_status_list"],
                }
            )
        return versions_and_statuses

    def _update_publish_data_parm(self, node, publish_data, version_policy):
        """
        Update the publish data parm on the node with the publish data and
        version policy.

        :param node: A :class:`hou.Node` instance.
        :param dict publish_data: The publish data.
        :param str version_policy: The version policy.
        """
        self.parent.logger.debug("VERSION_POLICY: %s", version_policy)
        publish_data["version_policy"] = version_policy
        for key, val in publish_data.items():
            # get rid of datetimes, they don't like to serialize and we don't need 'em
            if isinstance(val, datetime.datetime):
                publish_data.pop(key)

        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        sgtk_publish_data.set(json.dumps(publish_data))

    def _update_version_from_publish_data(self, node, publish_data, version_policy):
        """
        Update the version parameter from the given publish data and version policy.

        :param node: A :class:`hou.Node` instance.
        :param dict publish_data: The publish data.
        :param str version_policy: The version policy.
        """
        sgtk_version = node.parm(self.SGTK_VERSION)
        all_versions = self._extract_versions(
            self._resolve_all_versions_statuses(publish_data)
        )
        menu_items = all_versions + self.VERSION_POLICIES
        self.parent.logger.debug("MENU_ITEMS: %r", menu_items)
        if version_policy in self.VERSION_POLICIES:
            index = menu_items.index(version_policy)
        else:
            index = menu_items.index(publish_data["version_number"])
        sgtk_version.set(index)

    def populate_node_from_publish_data(self, node, publish_data, version_policy=None):
        """
        Populate the node from the given publish data.

        :param node: A :class:`hou.Node` instance.
        :param dict publish_data: The publish data.
        :param str version_policy: The version policy.
        """
        if publish_data:
            publish_data_is_list = isinstance(publish_data, list)
            if self.ACCEPTS_MULTI_SELECTION and not publish_data_is_list:
                publish_data = [publish_data]
            elif publish_data_is_list and not self.ACCEPTS_MULTI_SELECTION:
                publish_data = [publish_data]

        self._update_publish_data_parm(node, publish_data, version_policy)
        self._update_version_from_publish_data(node, publish_data, version_policy)
        self._refresh_file_path(node)

    def _load_from_shotgun(self, node):
        """
        Open a shotgun loader dialogue and populate the node from the selection made.

        :param node: A :class:`hou.Node` instance.
        """
        tk_multi_loader_app = self.parent.apps.get("tk-multi-loader2")
        if not tk_multi_loader_app:
            self.parent.logger.error("'tk-multi-loader2' not loaded")
            return
        tk_multi_loader = tk_multi_loader_app.import_module("tk_multi_loader")

        utils = self.parent.import_module("tk_houdini").utils
        action_manager = utils.HoudiniActionManager(self, node)

        widget = tk_multi_loader.dialog.AppDialog(
            action_manager, parent=hou.ui.mainQtWindow()
        )
        self.parent.apply_external_stylesheet(widget)
        widget.setWindowFlags(widget.windowFlags() | sgtk.platform.qt.QtCore.Qt.Window)
        widget.setWindowModality(sgtk.platform.qt.QtCore.Qt.WindowModal)
        action_manager.on_action_triggered.connect(widget.close)
        widget.show()

    def load_from_shotgun(self, kwargs):
        """
        Callback to open a shotgun loader dialogue and populate the node from the selection made.
        """
        node = kwargs["node"]
        self._load_from_shotgun(node)

    def _get_all_versions_and_statuses(self, node):
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        all_versions_json = sgtk_all_versions.evalAsString() or "[]"
        all_versions_and_statuses = json.loads(all_versions_json)
        return all_versions_and_statuses

    @staticmethod
    def _extract_versions(versions_and_statuses):
        """
        Extract just the versions from the versions and statuses dict.

        :param list(dict) versions_and_statuses: The versions and statuses.

        :rtype: list(int)
        """
        return [x["version"] for x in versions_and_statuses]

    def _get_all_versions(self, node):
        """
        Get all the available versions off the given node.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(int)
        """
        return self._extract_versions(self._get_all_versions_and_statuses(node))

    def _retrieve_publish_data(self, node):
        """
        Retrieve publish data off the given node.

        :param node: A :class:`hou.Node` instance.

        :rtype: dict
        """
        sgtk_publish_data = node.parm(self.SGTK_PUBLISH_DATA)
        default = "[]" if self.ACCEPTS_MULTI_SELECTION else "{}"
        publish_data_str = sgtk_publish_data.evalAsString() or default
        publish_data = json.loads(self._escape_publish_data(publish_data_str))
        self.parent.logger.debug("PUBLISH_DATA: %s", json.dumps(publish_data, indent=4))
        return publish_data

    def refresh_file_path_from_version(self, kwargs):
        """
        Callback to refresh the file paths generated by the node handler when the
        version is updated.
        """
        node = kwargs["node"]
        publish_data = self._retrieve_publish_data(node)
        sgtk_version = node.parm(self.SGTK_VERSION)
        version = sgtk_version.evalAsString()
        version_policy = version if version in self.VERSION_POLICIES else None
        self._update_publish_data_parm(node, publish_data, version_policy)
        super(ImportNodeHandler, self).refresh_file_path_from_version(kwargs)
        # now write the resolved version back to the publish data
        sgtk_resolved_version = node.parm(self.SGTK_RESOLVED_VERSION)
        resolved_version = sgtk_resolved_version.eval()
        publish_data["version_number"] = int(resolved_version)
        self._update_publish_data_parm(node, publish_data, version_policy)

    #############################################################################################
    # Utilities
    #############################################################################################

    def _remove_sgtk_items_from_parm_group(self, parameter_group):
        """
        Remove all sgtk parameters from the node's parameter template group.

        :param ParmGroup parameter_group: The parameter group containing sgtk parameters.
        """
        index = parameter_group.index_of_template(self.SGTK_FOLDER)
        parameter_group.pop_template(index)

    def _restore_sgtk_parms(self, node):
        """
        Restore any removed sgtk parameters onto the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.
        """
        input_parm = node.parm(self.INPUT_PARM)
        original_file_path = input_parm.unexpandedString()

        publish_data = self._retrieve_publish_data(node)
        self.add_sgtk_parms(node)
        all_versions_and_statuses = self._resolve_all_versions_statuses(publish_data)
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        sgtk_all_versions.set(json.dumps(all_versions_and_statuses))
        if publish_data:
            self.populate_node_from_publish_data(
                node, publish_data, publish_data["version_policy"]
            )

        sgtk_last_used = node.parm(self.SGTK_LAST_USED)
        if sgtk_last_used.eval():
            use_sgtk = node.parm(self.USE_SGTK)
            use_sgtk.set(True)
            self._enable_sgtk(node, True)
        else:
            input_parm.lock(False)
            input_parm.set(original_file_path)

    def get_input_paths(self, node):
        """
        Get all the input paths from the given node.

        :param node: A :class:`hou.Node` instance containing sgtk parameters.

        :rtype: list(str)
        """
        parm = node.parm(self.USE_SGTK)
        input_paths = []
        if parm and parm.eval():
            main_input = node.parm(self.INPUT_PARM)
            path = main_input.unexpandedString()
            input_paths.append(path)

        return input_paths
