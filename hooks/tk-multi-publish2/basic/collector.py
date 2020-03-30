# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import hou
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

# A dict of dicts organized by category, type and output file parm
_HOUDINI_OUTPUTS = {
    # rops
    hou.ropNodeTypeCategory(): [
        "alembic",  # alembic cache
        "geometry",  # geometry
        "ifd",  # mantra render node
        "arnold",  # arnold render node
    ],
}


def _iter_output_nodes():
    """Iterate over all output nodes in the scene.

    For a more functional programming approach, you can try::

        for category, type_names in _HOUDINI_OUTPUTS.items():
            node_types = (hou.nodeType(category, name) for name in type_names)
            for node_type in filter(None, node_types):  # Strip None node_type
                yield category, node_type, node_type.instances() or ()

    :return: Node category, node type and all node instances.
    :rtype: Generator[hou.NodeTypeCategory, hou.NodeType, tuple[hou.Node]]
    """
    for category, type_names in _HOUDINI_OUTPUTS.items():
        for name in type_names:
            node_type = hou.nodeType(category, name)
            if node_type is not None:
                yield category, node_type, node_type.instances() or ()


class HoudiniSessionCollector(HookBaseClass):
    """
    Collector that operates on the current houdini session. Should inherit from
    the basic collector hook.
    """

    def _get_icon_path(self, icon_name, icons_folders=None):
        icons_path = os.path.join(self.disk_location, "icons")
        if icons_folders:
            icons_folders.append(icons_path)
        else:
            icons_folders = [icons_path]
        return super(HoudiniSessionCollector, self)._get_icon_path(
            icon_name, icons_folders=icons_folders
        )

    @property
    def common_file_info(self):
        """Get a mapping of file types information.

        Sets up/stores it as `self._common_file_info` if not initialised.

        :return: File types information
        :rtype: dict[str, dict[str]]
        """
        if not hasattr(self, "_common_file_info"):

            # do this once to avoid unnecessary processing
            self._common_file_info = {
                "Alembic Cache": {
                    "extensions": ["abc"],
                    "icon": self._get_icon_path("alembic.png"),
                    "item_type": "file.alembic",
                },
                "Geometry Cache": {
                    "extensions": ["geo", "bgeo.sc", "sc", "vdb"],
                    "icon": self._get_icon_path("geometry.png"),
                    "item_type": "file.houdini.geometry",
                },
                "Rendered Image": {
                    "extensions": ["exr", "rat"],
                    "icon": self._get_icon_path("image_sequence.png"),
                    "item_type": "file.image",
                },
                "Ass File": {
                    "extensions": ["ass"],
                    "icon": self._get_icon_path("ass_file.png"),
                    "item_type": "file.arnold.ass",
                },
                "Ifd Cache": {
                    "extensions": ["ifd"],
                    "icon": self._get_icon_path("ifd_file.png"),
                    "item_type": "file.houdini.ifd",
                },
                "Material X File": {
                    "extensions": ["mtlx"],
                    "icon": self._get_icon_path("materialX.png"),
                    "item_type": "file.arnold.mtlx",
                },
            }

        return self._common_file_info

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(HoudiniSessionCollector, self).settings or {}

        # settings specific to this collector
        houdini_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": (
                    "Template path for artist work files. Should "
                    "correspond to a template defined in "
                    "templates.yml. If configured, is made available"
                    "to publish plugins via the collected item's "
                    "properties. "
                ),
            },
        }

        # update the base settings with these settings
        collector_settings.update(houdini_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current Houdini session and parents a subtree of items
        under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        # create an item representing the current houdini session
        item = self.collect_current_houdini_session(settings, parent_item)

        # collect other, non-toolkit outputs to present for publishing
        self.collect_node_outputs(settings, item)

    def collect_current_houdini_session(self, settings, parent_item):
        """
        Creates an item that represents the current houdini session.

        :param dict settings: Configured settings for this collector
        :param parent_item: Parent Item instance

        :returns: Item of type houdini.session
        """

        publisher = self.parent

        # get the path to the current file
        path = hou.hipFile.path()

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Houdini Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "houdini.session", "Houdini File", display_name
        )

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, "icons", "houdini.png")
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so that
        # it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            self.logger.debug("Work template defined for Houdini collection.")

        self.logger.info("Collected current Houdini session")
        return session_item

    def collect_node_outputs(self, settings, parent_item):
        """
        Creates items for known output nodes

        :param dict settings: Configured settings for this collector
        :param parent_item: Parent Item instance
        """

        engine = self.parent.engine

        for _, node_type, nodes in _iter_output_nodes():
            type_name = node_type.name()
            get_output_paths_and_templates = None
            # iterate over each node
            for node in nodes:
                if get_output_paths_and_templates is None:
                    get_output_paths_and_templates = getattr(
                        engine.node_handler(node),
                        "get_output_paths_and_templates",
                        None,
                    )
                    if get_output_paths_and_templates is None:
                        # This isn't an export node or missing handler
                        self.logger.info("%s node: %s", type_name, node.path())
                        break

                # get the evaluated path parm value
                self.logger.info("Processing %s node: %s", type_name, node.path())
                paths_and_templates = get_output_paths_and_templates(node)
                node_item = parent_item.create_item(
                    "houdini.node.{}".format(type_name), "", node.name()
                )

                for path_and_templates in paths_and_templates:
                    path = path_and_templates["path"]
                    # Check that something was generated
                    # Path might point to an image number that doesn't exist, so better
                    # check the sequence paths also as these have been found already
                    if not (
                        os.path.exists(path) or path_and_templates.get("sequence_paths")
                    ):
                        continue

                    is_sequence = "sequence_paths" in path_and_templates

                    # allow the base class to collect and create the item. it
                    # should know how to handle the output path
                    item = super(HoudiniSessionCollector, self)._collect_file(
                        node_item, path, frame_sequence=is_sequence
                    )

                    if (
                        item.type_spec == "file.image"
                        and "is_deep" in path_and_templates
                    ):
                        # Handle deep renders, which can only be exr files annoyingly
                        sequence = " Sequence" if is_sequence else ""
                        item.type_spec = "file.image.deep{}".format(
                            sequence.lower().replace(" ", ".")
                        )
                        item.name = "Deep Image{}".format(sequence)
                        item.properties["publish_type"] = "Deep Image"
                        item.set_icon_from_path(self._get_icon_path("deep_image.png"))

                    if is_sequence:
                        # self._collect_file doesn't fill in
                        # sequence_paths correctly so we must do it
                        sequence_paths = path_and_templates["sequence_paths"]
                        item.properties["sequence_paths"] = sequence_paths

                    template = path_and_templates["work_template"]
                    item.properties["work_template"] = template
                    item.properties["publish_template"] = path_and_templates[
                        "publish_template"
                    ]

                    fields = template.get_fields(path)

                    publish_name_tokens = []
                    for key in ["name", "location", "variation", "identifier"]:
                        token = fields.get(key)
                        if token:
                            publish_name_tokens.append(token.title())

                    publish_name = "{} ({})".format(
                        ", ".join(publish_name_tokens), item.type_display
                    )
                    item.properties["publish_name"] = publish_name
