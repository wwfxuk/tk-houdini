"""Base Hook for other Houdini import node handlers.

These include:

- ``alembic_import_handler``
- ``file_handler``
- ``image_handler``

"""
import datetime
import glob
import itertools
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
    SGTK_PATH_PUBLISH = "sgtk_path_selection1"
    SGTK_PATH_WORK = "sgtk_path_selection2"
    SGTK_PATH_FILE = "sgtk_path_selection3"
    SGTK_PATH_SELECTION = "sgtk_path_selection11"
    SGTK_WORK_FILE_DATA = "sgtk_work_file_data"
    SGTK_NODE_NAME = "sgtk_node_name"
    SGTK_NODE_PARM = "sgtk_node_parm"
    SGTK_WORK_VERSION = "sgtk_work_version"
    SGTK_WORK_REFRESH_VERSIONS = "sgtk_work_refresh_versions"
    SGTK_WORK_RESOLVED_VERSION = "sgtk_work_resolved_version"
    SGTK_FILE_DATA = "sgtk_file_data"
    SGTK_FILE_PATH = "sgtk_file_path"
    SGTK_FILE_VERSION = "sgtk_file_version"
    SGTK_FILE_REFRESH_VERSIONS = "sgtk_file_refresh_versions"
    SGTK_FILE_RESOLVED_VERSION = "sgtk_file_resolved_version"
    SGTK_CURRENT_TAB = "sgtk_current_tab"

    DEFAULT_WORK_FILE_DATA = json.dumps(
        {
            "node": None,
            "all_parms": [],
            "parm": None,
            "all_versions": [],
            "current_version": LATEST_POLICY,
        }
    )
    DEFAULT_FILE_DATA = json.dumps(
        {
            "path": None,
            "all_versions": [],
            "current_version": LATEST_POLICY,
        }
    )
    FILECHOOSER_PATTERN = "*"
    HOU_FILE_TYPE = hou.fileType.Any

    VALID_FILE_TYPES = "valid_file_types"

    ACCEPTS_MULTI_SELECTION = False

    PUBLISH, WORK, FILE = 0, 1, 2

    WORK_VERSION_TEMPLATE = "v{}"
    WORK_VERSION_REGEX = WORK_VERSION_TEMPLATE.format(r"(\d+)")
    SEQUENCE_REGEX = "-9999"  # This is a slight hack

    NO_VERSIONS = "No version"
    NO_PUBLISH = "No publish selected"
    NO_NODE = "No node selected"
    NO_FILE = "No file selected"
    NOTHING_ON_DISK = "Nothing on disk"

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

    def _path_selection(self, node):
        """
        Get the index of the current path selection.

        :param node: A :class:`hou.Node` instance.

        :rtype: int
        """
        parm = node.parm(self.SGTK_PATH_SELECTION)
        return parm.evalAsInt()

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
        sgtk_publish_data = hou.StringParmTemplate(
            self.SGTK_PUBLISH_DATA, "publish data", 1, is_hidden=True
        )
        parameter_group.append_template(sgtk_publish_data)

        sgtk_last_used = hou.ToggleParmTemplate(
            self.SGTK_LAST_USED,
            "shotgun last used",
            default_value=False,
            is_hidden=True,
        )
        parameter_group.append_template(sgtk_last_used)

        sgtk_work_file_data = hou.StringParmTemplate(
            self.SGTK_WORK_FILE_DATA,
            "work data",
            1,
            default_value=(self.DEFAULT_WORK_FILE_DATA,),
            is_hidden=True,
        )
        parameter_group.append_template(sgtk_work_file_data)

        sgtk_file_data = hou.StringParmTemplate(
            self.SGTK_FILE_DATA,
            "file data",
            1,
            default_value=(self.DEFAULT_FILE_DATA,),
            is_hidden=True,
        )
        parameter_group.append_template(sgtk_file_data)

        sgtk_current_tab = hou.IntParmTemplate(
            self.SGTK_CURRENT_TAB,
            "current tab",
            1,
            default_value=(0,),
            is_hidden=True,
        )
        parameter_group.append_template(sgtk_current_tab)

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

    def _create_sgtk_parm_fields(self, node, hou=None):
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

        templates = []

        ###################
        ### Publish Tab ###
        ###################
        publish_templates = super(ImportNodeHandler, self)._create_sgtk_parm_fields(
            node, hou=hou
        )

        publish_folder = hou.FolderParmTemplate(
            self.SGTK_PATH_PUBLISH,
            "Publish",
            parm_templates=publish_templates,
            folder_type=hou.folderType.RadioButtons,
        )
        publish_folder.setScriptCallback(
            self.generate_callback_script_str("refresh_from_selection")
        )
        publish_folder.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        templates.append(publish_folder)

        ###################
        #### Work Tab  ####
        ###################
        work_templates = []

        node_parm = hou.StringParmTemplate(
            self.SGTK_NODE_NAME,
            "Node",
            1,
            string_type=hou.stringParmType.NodeReference,
            script_callback=self.generate_callback_script_str(
                "refresh_from_node_selection"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        node_parm.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        work_templates.append(node_parm)

        parameter = hou.MenuParmTemplate(
            self.SGTK_NODE_PARM,
            "Parameter",
            tuple(),
            item_generator_script=self.generate_callback_script_str(
                "populate_node_parms_menu"
            ),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str(
                "refresh_from_parm_selection"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        parameter.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        work_templates.append(parameter)

        version = hou.MenuParmTemplate(
            self.SGTK_WORK_VERSION,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str(
                "populate_work_versions"
            ),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str(
                "refresh_from_work_version"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        version.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        version.setJoinWithNext(True)
        work_templates.append(version)

        refresh_button = hou.ButtonParmTemplate(
            self.SGTK_WORK_REFRESH_VERSIONS,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str("refresh_work_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        refresh_button.setConditional(
            hou.parmCondType.DisableWhen, '{ use_sgtk != 1 } { sgtk_node_name == "" }'
        )
        refresh_button.setJoinWithNext(True)
        work_templates.append(refresh_button)

        resolved_version = hou.StringParmTemplate(
            self.SGTK_WORK_RESOLVED_VERSION,
            "Resolved Version",
            1,
            default_value=(self.NO_VERSIONS,),
        )
        resolved_version.setConditional(
            hou.parmCondType.DisableWhen, "{ sgtk_version != -1 }"
        )
        work_templates.append(resolved_version)

        work_folder = hou.FolderParmTemplate(
            self.SGTK_PATH_WORK,
            "Work",
            parm_templates=work_templates,
            folder_type=hou.folderType.RadioButtons,
        )
        work_folder.setScriptCallback(
            self.generate_callback_script_str("refresh_from_selection")
        )
        work_folder.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        templates.append(work_folder)

        ###################
        #### File Tab  ####
        ###################
        file_templates = []

        path_parm = hou.StringParmTemplate(
            self.SGTK_FILE_PATH,
            "Path",
            1,
            string_type=hou.stringParmType.FileReference,
            file_type=self.HOU_FILE_TYPE,
            tags={"filechooser_pattern": self.FILECHOOSER_PATTERN},
            script_callback=self.generate_callback_script_str(
                "refresh_from_file_selection"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        path_parm.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        file_templates.append(path_parm)

        file_version = hou.MenuParmTemplate(
            self.SGTK_FILE_VERSION,
            "Version",
            tuple(),
            item_generator_script=self.generate_callback_script_str(
                "populate_file_versions"
            ),
            item_generator_script_language=hou.scriptLanguage.Python,
            script_callback=self.generate_callback_script_str(
                "refresh_from_file_version"
            ),
            script_callback_language=hou.scriptLanguage.Python,
        )
        file_version.setConditional(hou.parmCondType.DisableWhen, "{ use_sgtk != 1 }")
        file_version.setJoinWithNext(True)
        file_templates.append(file_version)

        file_refresh_button = hou.ButtonParmTemplate(
            self.SGTK_FILE_REFRESH_VERSIONS,
            "Refresh Versions",
            script_callback=self.generate_callback_script_str("refresh_from_file_path"),
            script_callback_language=hou.scriptLanguage.Python,
        )
        file_refresh_button.setConditional(
            hou.parmCondType.DisableWhen, '{ use_sgtk != 1 } { sgtk_file_path == "" }'
        )
        file_refresh_button.setJoinWithNext(True)
        file_templates.append(file_refresh_button)

        file_resolved_version = hou.StringParmTemplate(
            self.SGTK_FILE_RESOLVED_VERSION,
            "Resolved Version",
            1,
            default_value=(self.NO_VERSIONS,),
        )
        file_resolved_version.setConditional(
            hou.parmCondType.DisableWhen, "{ sgtk_version != -1 }"
        )
        file_templates.append(file_resolved_version)

        file_folder = hou.FolderParmTemplate(
            self.SGTK_PATH_FILE,
            "File",
            parm_templates=file_templates,
            folder_type=hou.folderType.RadioButtons,
        )
        file_folder.setScriptCallback(
            self.generate_callback_script_str("refresh_from_selection")
        )
        file_folder.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        templates.append(file_folder)

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
        if sgtk_enabled:
            selection = self._path_selection(node)
            if selection == self.PUBLISH:
                self._refresh_file_path(node)
            elif selection == self.WORK:
                self._refresh_file_path_from_node(node)
            else:
                self._refresh_file_path_from_path(node)

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

    #############################################################################################
    # Methods for populating from publish data
    #############################################################################################

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
        if self._validate_publish_data(publish_data):
            name = publish_data.get("name") or publish_data.get("code", "")
            sgtk_name = node.parm(self.SGTK_NAME)
            sgtk_name.set(name)

            all_versions_and_statuses = self._resolve_all_versions_statuses(
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
            result = sg.find_one("PublishedFile", filters, ["id", "path"]) or {}

            id_ = str(result.get("id", ""))
            sgtk_id = node.parm(self.SGTK_ID)
            sgtk_id.set(id_)

            if not result:
                path = "Failed to get publish entity"
            else:
                path = self._get_path_from_sg_data(result)
                path = self._convert_path_to_houdini_seq(path)
        else:
            path = self.NO_PUBLISH

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
        else:
            input_parm = node.parm(self.INPUT_PARM)
            input_parm.lock(False)
            input_parm.set(self.NO_PUBLISH)
            input_parm.lock(True)

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
    # Methods for populating from node
    #############################################################################################

    def _resolve_work_version(self, all_versions, current):
        """
        From a given string, resolve the current version.
        Either a specified version or the next version in the sequence.

        :param list(int) all_versions: All the existing versions.
        :param str current: The currently selected version option.

        :rtype: int or NoneType
        """
        if all_versions:
            resolved = max(all_versions)
            if current != self.LATEST_POLICY:
                current = int(current)
                if current in all_versions:
                    resolved = current
            return resolved

    def _get_template_fields_and_work_versions(self, parent_node, parm_name):
        """
        Get the template, template fields and all versions from the file path
        associated with the given node and parameter name.

        This method will initially use the node handler for the given node to
        retrieve the template, then falls back to :meth:`sgtk.Sgtk.template_from_path`.

        If no template can be found, all versions will be calculated using regexes
        that look for `v#` in the file path.

        :param parent_node: The node to retrieve the data from.
        :param parm_name: The name of the parameter that contains the file path.

        :returns: A :class:`tuple` of :class:`sgtk.Template`, dict and list(int)
        """
        all_versions = []
        template = None
        fields = {}
        if parent_node:
            path_parm = parent_node.parm(parm_name)
            if path_parm:
                path = path_parm.evalAsString()
                node_handler = self.parent.node_handler(parent_node)
                if node_handler and hasattr(node_handler, "OUTPUT_PARM"):
                    template = node_handler.get_work_template(parent_node)
                else:
                    try:
                        template = self.sgtk.template_from_path(path)
                    except sgtk.TankError:
                        template = None
                if template:
                    fields = template.validate_and_get_fields(path)
                    if fields:
                        if "SEQ" in fields:
                            fields["SEQ"] = "FORMAT: $F"
                        all_versions = node_handler._resolve_all_versions_from_fields(
                            fields, template
                        )
                else:
                    all_versions = self._resolve_all_versions_from_path(
                        path_parm.unexpandedString()
                    )
        return template, fields, all_versions

    def _refresh_file_path_from_node(self, node):
        """
        Use another node to populate the file path on this node.

        :param node: A :class:`hou.Node` instance.
        """
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        parent_parm = node.parm(self.SGTK_NODE_PARM)
        sgtk_resolved_version = node.parm(self.SGTK_WORK_RESOLVED_VERSION)
        node_path = work_file_data["node"]
        parent_node = hou.node(node_path)
        if parent_node:
            parent_node_parm = node.parm(self.SGTK_NODE_NAME)
            parent_node_parm.set(node_path)

            parm_name = work_file_data["parm"]
            all_parms = work_file_data["all_parms"]
            if all_parms:
                index = all_parms.index(parm_name)
            else:
                index = 0
            parent_parm.set(index)

            (
                template,
                fields,
                all_versions,
            ) = self._get_template_fields_and_work_versions(parent_node, parm_name)
            work_file_data["all_versions"] = all_versions
            work_file_parm.set(json.dumps(work_file_data))

            version = work_file_data["current_version"]
            resolved_version = self._resolve_work_version(all_versions, version)

            sgtk_resolved_version.set(str(resolved_version or self.NO_VERSIONS))

            path_parm = parent_node.parm(parm_name)
            orig_path = path_parm.unexpandedString()
            if resolved_version:
                if template:
                    fields["version"] = resolved_version
                    path = template.apply_fields(fields)
                else:
                    path = self._replace_version_in_path(orig_path, resolved_version)
            else:
                path = self.NOTHING_ON_DISK

        else:
            parent_parm.set(0)
            sgtk_version = node.parm(self.SGTK_WORK_VERSION)
            sgtk_version.set(0)
            sgtk_resolved_version.set(self.NO_VERSIONS)
            path = self.NO_NODE

        work_file_parm.set(json.dumps(work_file_data))
        input_parm = node.parm(self.INPUT_PARM)
        input_parm.lock(False)
        input_parm.set(path)
        input_parm.lock(True)

    def populate_node_parms_menu(self, kwargs):
        """
        Populate the parameter name menu.

        :rtype: list(str)
        """
        node = kwargs["node"]
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        parms = work_file_data.get("all_parms", [])
        return list(itertools.chain(*zip(parms, parms)))

    def _get_work_versions(self, node):
        """
        Get all the versions from the stored data on this node.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(int)
        """
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        all_versions = work_file_data.get("all_versions", [])
        return all_versions

    def populate_work_versions(self, kwargs):
        """
        Populate the work versions menu with all available versions and `<LATEST>`.

        :rtype: list(str)
        """
        node = kwargs["node"]
        versions = list(map(str, self._get_work_versions(node))) + [self.LATEST_POLICY]
        return list(itertools.chain(*zip(versions, versions)))

    def _get_node_file_parms(self, parent_node):
        """
        Get all the parameters on the given node that are of the type
        :class:`hou.stringParmType.FileReference`.

        :param parent_node: A :class:`hou.Node` instance.

        :rtype: list(str)
        """
        parms = []
        if parent_node:
            for parm in parent_node.parms():
                parm_template = parm.parmTemplate()
                if isinstance(parm_template, hou.StringParmTemplate):
                    if parm_template.stringType() == hou.stringParmType.FileReference:
                        parms.append(parm.name())
        return sorted(parms)

    def refresh_from_node_selection(self, kwargs):
        """
        Call back to refresh the file path when the node selection is changed.
        """
        node = kwargs["node"]
        parm = kwargs["parm"]
        parent_node = parm.evalAsNode()
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        if parent_node:
            work_file_data["node"] = parent_node.path()
            path_parm = node.parm(self.SGTK_NODE_PARM)
            node_handler = self.parent.node_handler(parent_node)
            parms = self._get_node_file_parms(parent_node)
            work_file_data["all_parms"] = parms
            index = 0
            parm_name = parms[0]
            if hasattr(node_handler, "OUTPUT_PARM"):
                parm_name = node_handler.OUTPUT_PARM
                index = parms.index(parm_name)
            work_file_data["parm"] = parm_name
            path_parm.set(index)
        work_file_parm.set(json.dumps(work_file_data))
        self._refresh_file_path_from_node(node)

    def refresh_from_parm_selection(self, kwargs):
        """
        Callback to refresh the file path when the parameter selection is changed.
        """
        node = kwargs["node"]
        parm = kwargs["parm"]
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        parent_node = hou.node(work_file_data["node"])
        parm_name = parm.evalAsString()
        work_file_data["parm"] = parm_name
        if parent_node:
            all_versions = self._get_template_fields_and_work_versions(
                parent_node, parm_name
            )[2]
            work_file_data["all_versions"] = all_versions
        work_file_parm.set(json.dumps(work_file_data))
        self._refresh_file_path_from_node(node)

    def refresh_from_work_version(self, kwargs):
        """
        Callback to refresh the file path when the work version parameter is changed.
        """
        node = kwargs["node"]
        parm = kwargs["parm"]
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        version = parm.evalAsString()
        work_file_data["current_version"] = version
        work_file_parm.set(json.dumps(work_file_data))
        self._refresh_file_path_from_node(node)

    def refresh_work_path(self, kwargs):
        """
        Callback to refresh the file path when the `Work` tab is active.
        """
        node = kwargs["node"]
        self._refresh_file_path_from_node(node)

    def _populate_from_work_file_data(self, node):
        """
        Populate the node's work file tab from the saved work file data.

        :param node: A :class:`hou.Node` instance.
        """
        work_file_parm = node.parm(self.SGTK_WORK_FILE_DATA)
        work_file_data = json.loads(
            work_file_parm.evalAsString() or self.DEFAULT_WORK_FILE_DATA
        )
        node_parm = node.parm(self.SGTK_NODE_NAME)
        node_parm.set(work_file_data["node"])

        parm_name = work_file_data["parm"]
        all_parms = work_file_data["all_parms"]
        if parm_name:
            index = all_parms.index(parm_name)
            parm_name_parm = node.parm(self.SGTK_NODE_PARM)
            parm_name_parm.set(index)

        version = work_file_data["current_version"]
        all_versions = list(map(str, work_file_data["all_versions"]))
        if version == self.LATEST_POLICY:
            index = len(all_versions)
        else:
            index = all_versions.index(version)
        version_parm = node.parm(self.SGTK_WORK_VERSION)
        version_parm.set(index)

        self._refresh_file_path_from_node(node)

    #############################################################################################
    # Methods for populating from file path
    #############################################################################################

    def _resolve_all_versions_from_path(self, path):
        """
        Extract all the versions on disk from the given file path.

        Looks for `v#` in the path to determine the version number.

        If the path exists on disk, but does not contain a version number, `1`
        will be returned. An empty list will be returned if no files exist on disk.

        :param path: The path to check against.

        :rtype: list(int)
        """
        unique_versions = set()
        expanded_path = hou.text.expandStringAtFrame(path, int(self.SEQUENCE_REGEX))
        regex = r"{}|{}".format(self.WORK_VERSION_REGEX, self.SEQUENCE_REGEX)
        glob_path = re.sub(regex, "*", expanded_path)
        at_least_one_version = False
        all_paths = glob.iglob(glob_path)
        for current_path in all_paths:
            at_least_one_version = True
            version_match = re.search(self.WORK_VERSION_REGEX, current_path)
            if version_match:
                unique_versions.add(int(version_match.group(1)))
        if at_least_one_version and not unique_versions:
            # the file exists on disk, but it does not contain a version number
            return [1]
        return list(unique_versions)

    def _replace_version_in_path(self, path, version):
        """
        Replace the version numbers in the file path with the given version.

        :param path: The old version path.
        :param version: The version number to update the path to.

        :return: The updated file path.
        """
        version_match = re.search(self.WORK_VERSION_REGEX, path)
        if version_match:
            current_version = version_match.group(1)
            if int(current_version) != version:
                pad = len(current_version)
                new_version = str(version).zfill(pad)
                new_version_str = self.WORK_VERSION_TEMPLATE.format(new_version)
                path = re.sub(self.WORK_VERSION_REGEX, new_version_str, path)
        return path

    def _get_file_versions(self, node):
        """
        Get all the file versions from the stored data on this node.

        :param node: A :class:`hou.Node` instance.

        :rtype: list(int)
        """
        file_data_parm = node.parm(self.SGTK_FILE_DATA)
        file_data = json.loads(file_data_parm.evalAsString() or self.DEFAULT_FILE_DATA)
        all_versions = file_data.get("all_versions", [])
        return all_versions

    def populate_file_versions(self, kwargs):
        """
        Populate the file versions menu with all available versions and `<LATEST>`.

        :rtype: list(str)
        """
        node = kwargs["node"]
        versions = list(map(str, self._get_file_versions(node))) + [self.LATEST_POLICY]
        return list(itertools.chain(*zip(versions, versions)))

    def _refresh_file_path_from_path(self, node):
        """
        Use another file path to update the file path on this node.

        :param node: A :class:`hou.Node` instance.
        """
        file_data_parm = node.parm(self.SGTK_FILE_DATA)
        file_data = json.loads(file_data_parm.evalAsString() or self.DEFAULT_FILE_DATA)
        file_parm = node.parm(self.SGTK_FILE_PATH)
        file_path = file_parm.unexpandedString()
        sgtk_resolved_version = node.parm(self.SGTK_FILE_RESOLVED_VERSION)
        if file_path:
            all_versions = self._resolve_all_versions_from_path(file_path)
            file_data["all_versions"] = all_versions
            file_data_parm.set(json.dumps(file_data))

            version = file_data["current_version"]
            resolved_version = self._resolve_work_version(all_versions, version)
            sgtk_resolved_version.set(str(resolved_version or self.NO_VERSIONS))
            if resolved_version:
                path = self._replace_version_in_path(file_path, resolved_version)
                file_parm.set(path)
            else:
                path = self.NOTHING_ON_DISK
        else:
            file_parm.set("")
            sgtk_version = node.parm(self.SGTK_FILE_VERSION)
            sgtk_version.set(0)
            sgtk_resolved_version.set(self.NO_VERSIONS)
            path = self.NO_FILE

        file_data_parm.set(json.dumps(file_data))
        input_parm = node.parm(self.INPUT_PARM)
        input_parm.lock(False)
        input_parm.set(path)
        input_parm.lock(True)

    def refresh_from_file_path(self, kwargs):
        """
        Callback to refresh the file path when the `File` tab is active.
        """
        node = kwargs["node"]
        self._refresh_file_path_from_path(node)

    def refresh_from_file_version(self, kwargs):
        """
        Callback to refresh the file path when the file version parameter is changed.
        """
        node = kwargs["node"]
        parm = kwargs["parm"]
        file_data_parm = node.parm(self.SGTK_FILE_DATA)
        file_data = json.loads(file_data_parm.evalAsString() or self.DEFAULT_FILE_DATA)
        version = parm.evalAsString()
        file_data["current_version"] = version
        file_data_parm.set(json.dumps(file_data))
        self._refresh_file_path_from_path(node)

    def refresh_from_file_selection(self, kwargs):
        """
        Callback to refresh the node's file path when the file selection is changed.
        """
        node = kwargs["node"]
        parm = kwargs["parm"]
        file_path = parm.unexpandedString()
        file_data_parm = node.parm(self.SGTK_FILE_DATA)
        file_data = json.loads(file_data_parm.evalAsString() or self.DEFAULT_FILE_DATA)
        if file_path:
            file_data["path"] = file_path
            all_versions = self._resolve_all_versions_from_path(file_path)
            file_data["all_versions"] = all_versions
            version_match = re.search(self.WORK_VERSION_REGEX, file_path)
            if version_match:
                version = int(version_match.group(1))
                file_data["current_version"] = version
                version_parm = node.parm(self.SGTK_FILE_VERSION)
                index = all_versions.index(version)
                version_parm.set(index)
        file_data_parm.set(json.dumps(file_data))
        self._refresh_file_path_from_path(node)

    def _populate_from_file_data(self, node):
        """
        Populate the node's File tab from the saved file data.

        :param node: A :class:`hou.Node` instance.
        """
        work_file_parm = node.parm(self.SGTK_FILE_DATA)
        file_data = json.loads(work_file_parm.evalAsString() or self.DEFAULT_FILE_DATA)
        path_parm = node.parm(self.SGTK_FILE_PATH)
        path_parm.set(file_data["path"])

        version = file_data["current_version"]
        all_versions = list(map(str, file_data["all_versions"]))
        if version == self.LATEST_POLICY:
            index = len(all_versions)
        else:
            index = all_versions.index(version)
        version_parm = node.parm(self.SGTK_FILE_VERSION)
        version_parm.set(index)

        self._refresh_file_path_from_path(node)

    def refresh_from_selection(self, kwargs):
        """
        Callback to refresh the node's file path when the tab selection changes.
        """
        node = kwargs["node"]
        sgtk_enabled = node.parm(self.USE_SGTK)
        if sgtk_enabled.eval():
            sgtk_current_tab = node.parm(self.SGTK_CURRENT_TAB)
            current_selection = self._path_selection(node)
            sgtk_current_tab.set(current_selection)
            if current_selection == self.PUBLISH:
                self._refresh_file_path(node)
            elif current_selection == self.WORK:
                self._refresh_file_path_from_node(node)
            else:
                self._refresh_file_path_from_path(node)

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

        current_tab_parm = node.parm(self.SGTK_CURRENT_TAB)
        current_tab_index = current_tab_parm.eval()

        publish_data = self._retrieve_publish_data(node)
        self.add_sgtk_parms(node)
        all_versions_and_statuses = self._resolve_all_versions_statuses(publish_data)
        sgtk_all_versions = node.parm(self.SGTK_ALL_VERSIONS)
        sgtk_all_versions.set(json.dumps(all_versions_and_statuses))

        if publish_data:
            self.populate_node_from_publish_data(
                node, publish_data, publish_data["version_policy"]
            )

        self._populate_from_work_file_data(node)
        self._populate_from_file_data(node)

        sgtk_path_selection = node.parm(self.SGTK_PATH_SELECTION)
        sgtk_path_selection.set(current_tab_index)

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
