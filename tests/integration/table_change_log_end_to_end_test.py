# -*- coding: utf-8 -*-
# Copyright 2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import absolute_import
from __future__ import unicode_literals

import pytest
from data_pipeline.message_type import MessageType

from replication_handler.environment_configs import is_envvar_set
from replication_handler.testing_helper.util import execute_query_get_one_row
from replication_handler.testing_helper.util import increment_heartbeat
from tests.integration.conftest import _fetch_messages
from tests.integration.conftest import _generate_basic_model
from tests.integration.conftest import _verify_messages


pytestmark = pytest.mark.usefixtures("cleanup_avro_cache")


@pytest.fixture(scope='module')
def replhandler():
    return 'replicationhandlerchangelog'


@pytest.fixture(scope='module')
def namespace():
    return 'changelog.v2'


@pytest.fixture(scope='module')
def source():
    return 'changelog_schema'


@pytest.mark.itest
@pytest.mark.skipif(
    is_envvar_set('OPEN_SOURCE_MODE'),
    reason="skip this in open source mode."
)
def test_change_log_messages(
    containers,
    rbrsource,
    create_table_query,
    schematizer,
    namespace,
    source,
    rbr_source_session,
    gtid_enabled
):

    if not gtid_enabled:
        increment_heartbeat(containers, rbrsource)

    execute_query_get_one_row(
        containers,
        rbrsource,
        create_table_query.format(table_name=source)
    )

    BasicModel = _generate_basic_model(source)
    model_1 = BasicModel(id=1, name='insert')
    model_2 = BasicModel(id=2, name='insert')
    rbr_source_session.add(model_1)
    rbr_source_session.add(model_2)
    rbr_source_session.commit()
    model_1.name = 'update'
    rbr_source_session.delete(model_2)
    rbr_source_session.commit()

    messages = _fetch_messages(
        containers,
        schematizer,
        namespace,
        source,
        4
    )

    expected_messages = [
        {
            'message_type': MessageType.create,
            'payload_data': {'id': 1, 'table_name': source, 'table_schema': 'yelp'}
        },
        {
            'message_type': MessageType.create,
            'payload_data': {'id': 2, 'table_name': source, 'table_schema': 'yelp'}
        },
        {
            'message_type': MessageType.update,
            'payload_data': {'id': 1, 'table_name': source, 'table_schema': 'yelp'},
            'previous_payload_data': {'id': 1, 'table_name': source, 'table_schema': 'yelp'}
        },
        {
            'message_type': MessageType.delete,
            'payload_data': {'id': 2, 'table_name': source, 'table_schema': 'yelp'}
        },
    ]
    _verify_messages(messages, expected_messages)
