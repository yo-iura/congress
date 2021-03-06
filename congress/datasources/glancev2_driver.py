# Copyright (c) 2014 VMware, Inc. All rights reserved.
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

import glanceclient.v2.client as glclient
from oslo_log import log as logging

from congress.datasources import constants
from congress.datasources import datasource_driver
from congress.datasources import datasource_utils as ds_utils

LOG = logging.getLogger(__name__)


class GlanceV2Driver(datasource_driver.PollingDataSourceDriver,
                     datasource_driver.ExecutionDriver):

    IMAGES = "images"
    TAGS = "tags"

    value_trans = {'translation-type': 'VALUE'}
    images_translator = {
        'translation-type': 'HDICT',
        'table-name': IMAGES,
        'selector-type': 'DICT_SELECTOR',
        'field-translators':
            ({'fieldname': 'id', 'desc': 'UUID of image',
              'translator': value_trans},
             {'fieldname': 'status', 'desc': 'The image status',
              'translator': value_trans},
             {'fieldname': 'name',
              'desc': 'Image Name', 'translator': value_trans},
             {'fieldname': 'container_format',
              'desc': 'The container format of image',
              'translator': value_trans},
             {'fieldname': 'created_at',
              'desc': 'The date and time when the resource was created',
              'translator': value_trans},
             {'fieldname': 'updated_at',
              'desc': 'The date and time when the resource was updated.',
              'translator': value_trans},
             {'fieldname': 'disk_format',
              'desc': 'The disk format of the image.',
              'translator': value_trans},
             {'fieldname': 'owner',
              'desc': 'The ID of the owner or tenant of the image',
              'translator': value_trans},
             {'fieldname': 'protected',
              'desc': 'Indicates whether the image can be deleted.',
              'translator': value_trans},
             {'fieldname': 'min_ram',
              'desc': 'minimum amount of RAM in MB required to boot the image',
              'translator': value_trans},
             {'fieldname': 'min_disk',
              'desc': 'minimum disk size in GB required to boot the image',
              'translator': value_trans},
             {'fieldname': 'checksum', 'desc': 'Hash of the image data used',
              'translator': value_trans},
             {'fieldname': 'size',
              'desc': 'The size of the image data, in bytes.',
              'translator': value_trans},
             {'fieldname': 'file',
              'desc': 'URL for the virtual machine image file',
              'translator': value_trans},
             {'fieldname': 'kernel_id', 'desc': 'kernel id',
              'translator': value_trans},
             {'fieldname': 'ramdisk_id', 'desc': 'ramdisk id',
              'translator': value_trans},
             {'fieldname': 'schema',
              'desc': 'URL for schema of the virtual machine image',
              'translator': value_trans},
             {'fieldname': 'visibility', 'desc': 'The image visibility',
              'translator': value_trans},
             {'fieldname': 'tags',
              'translator': {'translation-type': 'LIST',
                             'table-name': TAGS,
                             'val-col': 'tag',
                             'val-col-desc': 'List of image tags',
                             'parent-key': 'id',
                             'parent-col-name': 'image_id',
                             'parent-key-desc': 'UUID of image',
                             'translator': value_trans}})}

    TRANSLATORS = [images_translator]

    def __init__(self, name='', args=None):
        super(GlanceV2Driver, self).__init__(name, args=args)
        datasource_driver.ExecutionDriver.__init__(self)
        self.creds = args
        session = ds_utils.get_keystone_session(self.creds)
        self.glance = glclient.Client(session=session)
        self.add_executable_client_methods(self.glance, 'glanceclient.v2.')
        self.initialize_update_methods()
        self._init_end_start_poll()

    @staticmethod
    def get_datasource_info():
        result = {}
        result['id'] = 'glancev2'
        result['description'] = ('Datasource driver that interfaces with '
                                 'OpenStack Images aka Glance.')
        result['config'] = ds_utils.get_openstack_required_config()
        result['config']['lazy_tables'] = constants.OPTIONAL
        result['secret'] = ['password']
        return result

    def initialize_update_methods(self):
        images_method = lambda: self._translate_images(
            {'images': self.glance.images.list()})
        self.add_update_method(images_method, self.images_translator)

    @ds_utils.update_state_on_changed(IMAGES)
    def _translate_images(self, obj):
        """Translate the images represented by OBJ into tables."""
        LOG.debug("IMAGES: %s", str(dict(obj)))
        row_data = GlanceV2Driver.convert_objs(
            obj['images'], GlanceV2Driver.images_translator)
        return row_data

    def execute(self, action, action_args):
        """Overwrite ExecutionDriver.execute()."""
        # action can be written as a method or an API call.
        func = getattr(self, action, None)
        if func and self.is_executable(func):
            func(action_args)
        else:
            self._execute_api(self.glance, action, action_args)
