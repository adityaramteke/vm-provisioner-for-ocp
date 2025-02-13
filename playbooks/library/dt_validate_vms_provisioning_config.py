#!/usr/bin/env python

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community',
}

DOCUMENTATION = '''
---
module: dt_validate_vms_provisioning_config

short_description: validates config options for OpenShift deployment tool

version_added: "2.4"

description:
    - "validates config options for OpenShift deployment tool"

options:
    path:
        description:
            - Path to config file, which should be validated.
        required: true
    check_groups:
        description:
            - List of top-level config options to validate.
        required: false

extends_documentation_fragment:

author:
    - Valerii Ponomarov (@vponomar)
'''

EXAMPLES = '''
- name: Read and validate whole config file
  dt_validate_vms_provisioning_config:
    path: "/fake/path/to/config/file.yaml"
  register: config_output

- name: Read and validate part of a config file
  dt_validate_vms_provisioning_config:
    path: "/fake/path/to/config/file.yaml"
    check_groups: ['common', 'vms']
  register: config_output
'''

RETURN = '''
config:
    description: Dictionary with validated data and inserted in default values.
    type: dict
'''

import schema
import yaml

from ansible.module_utils.basic import AnsibleModule


def validate_config_structure(module, config):
    def non_empty_string_without_spaces(input_string):
        if ' ' in input_string or not input_string.strip():
            {}['Repository name should not be empty and should not contain '
               '"space" symbols.']
        return input_string

    node_types = ("all", "masters", "nodes", "glusterfs", "glusterfs_registry")
    vm_repo_downstream_default = {
        "skip": True,
        "repositories_to_enable": {
            "all": [], "masters": [], "nodes": [], "glusterfs": [],
            "glusterfs_registry": [],
        },
    }
    cluster_validation_default = dict(
        {"skip": True}.items() +
        {pod_type: {
            "redhat_storage_release": None,
            "redhat_release": None,
            "packages": [],
            "validate_package_signatures": True,
        } for pod_type in ("heketi_pod", "gluster_pod",
                           "gluster_block_provisioner_pod")}.items()
    )
    common_default = {
        "output_tests_config_file": "../tests_config.yaml",
        "output_cluster_info_file": "../cluster_info.yaml",
    }
    config_schema_dict = {
        "vmware": {
            "host": schema.And(str, len),
            "username": schema.And(str, len),
            "password": schema.And(str, len),
            "datacenter": schema.And(str, len),
            "cluster": schema.And(str, len),
            "resource_pool": schema.And(str, len),
            "folder": schema.And(str, len),
            "datastore": schema.And(str, len),
            "vm_network": schema.And(str, len),
            "vm_templates": [schema.And(str, len)],
            "vm_parameters": {node_type: {
                schema.Optional("num_cpus", default=1): schema.And(
                    int, lambda i: i in range(1, 17)),
                schema.Optional("ram_mb", default=16384): schema.And(
                    int, lambda i: 4096 <= i <= 65535),
                schema.Optional("names", default=[]): schema.Or(
                    schema.Use(lambda o: (
                        [] if (o is None or o == []) else {}[
                            "Only 'None' or 'list' objects are allowed"]
                    )),
                    schema.And([schema.And(str, len)], lambda l: len(l) <= 9),
                ),
                schema.Optional("system_disks_gb", default=[150]): schema.And(
                    [schema.And(int, lambda i: 0 < i)],
                    lambda l: len(l) <= 4),
                schema.Optional("system_disks_type", default='thin'): (
                    schema.And(str, len)),
                schema.Optional("storage_disks_gb", default=(
                    [100, 600, 100] if 'gluster' in node_type else []
                )): schema.And(
                    [schema.And(int, lambda i: 0 < i)], lambda l: len(l) <= 7),
                schema.Optional("storage_disks_type", default='thin'): (
                    schema.And(str, len))
            } for node_type in node_types if node_type != "all"}
        },
        "vm": {
            "repo": {
                "upstream": {
                    schema.Optional("skip", default=True): bool,
                    schema.Optional("subscription_server",
                                    default="not_set"): schema.Or(
                        schema.And(str, len), None),
                    schema.Optional("subscription_baseurl",
                                    default="not_set"): schema.Or(
                        schema.And(str, len), None),
                    schema.Optional("subscription_user",
                                    default="not_set"): schema.Or(
                        schema.And(str, len), None),
                    schema.Optional("subscription_pass",
                                    default="not_set"): schema.Or(
                        schema.And(str, len), None),
                    schema.Optional("subscription_pool",
                                    default="not_set"): schema.Or(
                        schema.And(str, len), None),
                    schema.Optional("repositories_to_enable",
                                    default={"all": [], "masters": [],
                                             "nodes": [], "glusterfs": [],
                                             "glusterfs_registry": []}): schema.Or({
                        schema.Optional(node_type, default=[]): schema.Or(
                            schema.Use(lambda o: ([] if o is None else {}[
                                "Only 'None' or 'list' objects are allowed"]
                            )), [schema.And(str, len)],
                        ) for node_type in node_types
                    }, None),
                },
                "downstream": schema.Or({
                    schema.Optional("skip", default=True): bool,
                    schema.Optional("repositories_to_enable",
                                    default=vm_repo_downstream_default[
                                        "repositories_to_enable"]): schema.Or(
                        schema.Use(lambda o: (
                            vm_repo_downstream_default["repositories_to_enable"]
                            if (o is None or o == {}) else {}[
                                "Only 'None' or 'dict' objects are allowed"])),
                        {
                            schema.Optional(node_type, default=[]): schema.Or(
                                schema.Use(lambda o: ([] if (o is None or o == []) else {}[
                                    "Only 'None' or 'list' objects are allowed"])),
                                [{
                                    "name": schema.And(
                                        str, non_empty_string_without_spaces),
                                    "url": schema.And(str, lambda s: 'http' in s),
                                    "cost": schema.And(int, lambda i: 0 < i),
                                }],
                            ) for node_type in node_types
                        }
                    ),
                }),
            },
            "yum": {
                schema.Optional("update", default=True): bool,
                schema.Optional("reboot_after_update", default=True): bool,
                schema.Optional("sleep_after_reboot_sec", default=60): int,
            },
            "uninstall_packages": schema.Or(
                schema.Use(lambda o: (
                    {"all": [], "masters": [], "nodes": [], "glusterfs": [],
                     "glusterfs_registry": []}
                    if (o is None or o == {}) else {}[
                        "Only 'None' or 'dict' objects are allowed"]
                )),
                {
                    schema.Optional(node_type, default=[]): schema.Or(
                        [schema.And(str, len)],
                        schema.Use(lambda o: (
                            [] if o is None else {}[
                                "Only 'None' or 'str' objects are allowed"]
                        ))
                    ) for node_type in node_types
                },
            ),
            "install_packages": schema.Or(
                schema.Use(lambda o: (
                    {"all": [], "masters": [], "nodes": [], "glusterfs": [],
                     "glusterfs_registry": []}
                    if o is None else {}[
                        "Only 'None' or 'dict' objects are allowed"]
                )),
                {
                    schema.Optional(node_type, default=[]): schema.Or(
                        [schema.And(str, len)],
                        schema.Use(lambda o: (
                            [] if o is None else {}[
                                "Only 'None' or 'str' objects are allowed"]
                        ))
                    ) for node_type in node_types
                },
            ),
            "setup_and_configuration": {
                schema.Optional("setup_common_packages",
                                default=True): bool,
                schema.Optional("setup_ntp", default=True): bool,
                schema.Optional("setup_vmware_tools", default=True): bool,
                schema.Optional("mount_disks", default=[]): schema.Or(
                    [{
                        "disk_path": schema.And(
                            str, lambda s: s.startswith("/dev/")),
                        "mount_point": schema.And(
                            str, lambda s: s.startswith("/")),
                        "name_prefix": schema.And(str, len),
                        "fstype": schema.And(str, len),
                    }],
                    schema.Use(lambda o: ([] if o is None else {}[
                        "Only 'None' or 'list' objects are allowed"])),
                ),
                schema.Optional("setup_docker_storage",
                                default={"skip": True, "disk_path": None}): {
                    schema.Optional("skip", default=True): bool,
                    schema.Optional("disk_path", default=None): (
                        schema.And(str, len)),
                },
                schema.Optional("setup_standalone_glusterfs",
                                default=False): bool,
                schema.Optional("setup_standalone_glusterfs_registry",
                                default=False): bool,
            },
        },
        "ocp_update": {
            "heketi": {
                schema.Optional("install_client_on_masters", default=True): bool,
                schema.Optional("client_package_url", default=None): (
                    schema.Use(lambda o: (
                        o.strip() if o and len(o.strip()) > 0 else None
                    ))
                ),
                schema.Optional("add_public_ip_address", default=True): bool,
            },
        },
        schema.Optional("cluster_validation",
                        default=cluster_validation_default): schema.Or(
            schema.Use(lambda o: (
                cluster_validation_default
                if not o else {}["Data is provided. Switch to filter."]
            )),
            dict(
                {schema.Optional(
                    "skip",
                    default=cluster_validation_default["skip"]): bool}.items() +
                {schema.Optional(pod_type, default=cluster_validation_default[
                        pod_type]): schema.Or(
                    schema.Use(lambda o: (
                        cluster_validation_default[pod_type]
                        if not o else {}["Data is provided. Skipping."]
                    )),
                    {schema.Optional("redhat_storage_release", default=None): (
                         schema.Use(lambda o: (
                             o.strip() if o and len(o.strip()) > 0 else None
                         ))
                     ),
                     schema.Optional("redhat_release", default=None): (
                         schema.Use(lambda o: (
                             o.strip() if o and len(o.strip()) > 0 else None
                         ))
                     ),
                     schema.Optional("packages", default=[]): schema.Or(
                         [schema.And(str, len)],
                         schema.Use(lambda o: (
                             [] if o is None else {}[
                                 "Only 'None' or 'list' of 'str'ings are allowed"]
                         ))
                     ),
                     schema.Optional("validate_package_signatures",
                                     default=True): bool,
                    }
                ) for pod_type in ("heketi_pod", "gluster_pod",
                                   "gluster_block_provisioner_pod")}.items()
            ),
        ),
        schema.Optional("tests_config_updates", default={}): schema.Or(
            schema.Use(lambda o: (
                {"common.allow_heketi_zones_update": False,
                 "common.stop_on_first_failure": False}
                if (o is None) else {}[
                    "Only 'dict' and 'None' values are allowed"])
            ),
            schema.Use(lambda o: (
                o if isinstance(o, dict) else {}[
                    "Only 'dict' and 'None' values are allowed"])
            ),
        ),
        "common": schema.Or(
            schema.Use(lambda o: (
                {"output_tests_config_file": common_default["output_tests_config_file"],
                 "output_cluster_info_file": common_default["output_cluster_info_file"]}
                if (o is None or o == {}) else {}[
                    "Only 'dict' and 'None' values are allowed"])
            ),
            {schema.Optional("output_tests_config_file",
                             default=(common_default["output_tests_config_file"])): (
                 schema.And(str, len)),
             schema.Optional("output_cluster_info_file",
                             default=(common_default["output_cluster_info_file"])): (
                 schema.And(str, len)),
            },
        ),
    }
    if module.params["check_groups"]:
        config_schema_dict = {
            k:v for k, v in config_schema_dict.items()
            if getattr(k, 'key', k) in module.params["check_groups"]}
        config_schema = schema.Schema(
            config_schema_dict, ignore_extra_keys=True)
    else:
        config_schema = schema.Schema(config_schema_dict)

    try:
        validated_config = config_schema.validate(config)
    except schema.SchemaError as e:
        module.fail_json(msg=("Error: %s" % e))
    return validated_config


def main():
    module_args = {
        "path": {"type": "str", "required": True},
        "check_groups": {"type": "list", "required": False},
    }
    result = {"config": ""}
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    if module.check_mode:
        return result

    # Make sure file was provided, it exists and yaml-parsible
    if not (module.params['path'] and module.params['path'].strip()):
        module.fail_json(msg="Path for config file is not provided")
    with open(module.params['path'], 'r') as config_stream:
        try:
            config = yaml.load(config_stream)
        except yaml.YAMLError as e:
            module.fail_json(
                msg=("Failed to parse '%s' file as yaml. "
                     "Got following error: %s") % (module.params['path'], e))

    # Validate config structure after successful parsing of the file
    validated_config = validate_config_structure(module, config)

    # Finish module execution
    result["config"] = validated_config
    module.exit_json(**result)


if __name__ == '__main__':
    main()
