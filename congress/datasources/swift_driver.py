# Copyright (c) 2014 Montavista Software, LLC.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from oslo_log import log as logging
import swiftclient.service

from congress.datasources import constants
from congress.datasources import datasource_driver
from congress.datasources import datasource_utils as ds_utils

LOG = logging.getLogger(__name__)


class SwiftDriver(datasource_driver.PollingDataSourceDriver,
                  datasource_driver.ExecutionDriver):

    CONTAINERS = "containers"
    OBJECTS = "objects"

    value_trans = {'translation-type': 'VALUE'}

    containers_translator = {
        'translation-type': 'HDICT',
        'table-name': CONTAINERS,
        'selector-type': 'DICT_SELECTOR',
        'field-translators':
            ({'fieldname': 'count', 'translator': value_trans},
             {'fieldname': 'bytes', 'translator': value_trans},
             {'fieldname': 'name', 'translator': value_trans})}

    objects_translator = {
        'translation-type': 'HDICT',
        'table-name': OBJECTS,
        'selector-type': 'DICT_SELECTOR',
        'field-translators':
            ({'fieldname': 'bytes', 'translator': value_trans},
             {'fieldname': 'last_modified', 'translator': value_trans},
             {'fieldname': 'hash', 'translator': value_trans},
             {'fieldname': 'name', 'translator': value_trans},
             {'fieldname': 'content_type', 'translator': value_trans},
             {'fieldname': 'container_name', 'translator': value_trans})}

    TRANSLATORS = [containers_translator, objects_translator]

    def __init__(self, name='', args=None):
        if args is None:
            args = self.empty_credentials()
        super(SwiftDriver, self).__init__(name, args=args)
        datasource_driver.ExecutionDriver.__init__(self)
        options = self.get_swift_credentials_v1(args)
        # TODO(ramineni): Enable v3 support
        options['os_auth_url'] = options['os_auth_url'].replace('v3', 'v2.0')
        self.swift_service = swiftclient.service.SwiftService(options)
        self.add_executable_client_methods(self.swift_service,
                                           'swiftclient.service')
        self.initialize_update_methods()
        self._init_end_start_poll()

    @staticmethod
    def get_datasource_info():
        # TODO(zhenzanz): This is verified with keystoneauth for swift.
        # Do we need to support other Swift auth systems?
        # http://docs.openstack.org/developer/swift/overview_auth.html
        result = {}
        result['id'] = 'swift'
        result['description'] = ('Datasource driver that interfaces with '
                                 'swift.')
        result['config'] = ds_utils.get_openstack_required_config()
        result['config']['lazy_tables'] = constants.OPTIONAL
        result['secret'] = ['password']
        return result

    def get_swift_credentials_v1(self, creds):
        # Check swiftclient/service.py _default_global_options for more
        # auth options. But these 4 options seem to be enough.
        options = {}
        options['os_username'] = creds['username']
        options['os_password'] = creds['password']
        options['os_tenant_name'] = creds['tenant_name']
        options['os_auth_url'] = creds['auth_url']
        return options

    def initialize_update_methods(self):
        containers_method = lambda: self._translate_containers(
            self._get_containers_and_objects(container=True))
        self.add_update_method(containers_method, self.containers_translator)

        objects_method = lambda: self._translate_objects(
            self._get_containers_and_objects(objects=True))
        self.add_update_method(objects_method, self.objects_translator)

    def _get_containers_and_objects(self, container=False, objects=False):
        container_list = self.swift_service.list()
        cont_list = []
        objects = []
        containers = []
        LOG.debug("Swift obtaining containers List")
        for stats in container_list:
            containers = stats['listing']
            for item in containers:
                cont_list.append(item['name'])
        if container:
            return containers
        LOG.debug("Swift obtaining objects List")
        for container in cont_list:
            object_list = self.swift_service.list(container)
            for items in object_list:
                item_list = items['listing']
                for obj in item_list:
                    obj['container_name'] = container
                for obj in item_list:
                    objects.append(obj)
        if objects:
            return objects
        return containers, objects

    @ds_utils.update_state_on_changed(CONTAINERS)
    def _translate_containers(self, obj):
        """Translate the containers represented by OBJ into tables."""
        row_data = SwiftDriver.convert_objs(obj,
                                            self.containers_translator)
        return row_data

    @ds_utils.update_state_on_changed(OBJECTS)
    def _translate_objects(self, obj):
        """Translate the objects represented by OBJ into tables."""
        row_data = SwiftDriver.convert_objs(obj,
                                            self.objects_translator)
        return row_data

    def execute(self, action, action_args):
        """Overwrite ExecutionDriver.execute()."""
        # action can be written as a method or an API call.
        func = getattr(self, action, None)
        if func and self.is_executable(func):
            func(action_args)
        else:
            self._execute_api(self.swift_service, action, action_args)
