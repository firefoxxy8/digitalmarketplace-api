# -*- coding: UTF-8 -*-
from datetime import datetime
from itertools import chain, repeat
import mock
import pytest
from nose.tools import assert_equal, assert_in, assert_true, assert_false
from flask import json
from six.moves import zip as izip
from six.moves.urllib.parse import urlencode
from freezegun import freeze_time

from dmapiclient.audit import AuditTypes

from app import db
from app.models import AuditEvent
from app.models import Supplier, Service
from tests.bases import BaseApplicationTest
from tests.helpers import FixtureMixin


class BaseTestAuditEvents(BaseApplicationTest, FixtureMixin):
    @staticmethod
    def audit_event(user=0, type=AuditTypes.supplier_update, db_object=None):
        return AuditEvent(
            audit_type=type,
            db_object=db_object,
            user=user,
            data={'request': "data"}
        )

    def add_audit_event(self, user=0, type=AuditTypes.supplier_update, db_object=None):
        with self.app.app_context():
            ae = self.audit_event(user, type, db_object)
            db.session.add(
                ae
            )
            db.session.commit()
            return ae.id

    def add_audit_events(self, number, type=AuditTypes.supplier_update, db_object=None):
        ids = []
        for user_id in range(number):
            ids.append(self.add_audit_event(user=user_id, type=type, db_object=db_object))
        return ids

    def add_audit_events_with_db_object(self):
        self.setup_dummy_suppliers(3)
        events = []
        with self.app.app_context():
            suppliers = Supplier.query.all()
            for supplier in suppliers:
                event = AuditEvent(AuditTypes.contact_update, "rob", {}, supplier)
                events.append(event)
                db.session.add(event)
            db.session.commit()
            return tuple(event.id for event in events)

    def add_audit_events_by_param_tuples(self, service_audit_event_params, supplier_audit_event_params):
        with self.app.app_context():
            # some migrations create audit events, but we want to start with a clean slate
            AuditEvent.query.delete()
            service_ids = db.session.query(Service.id).order_by(Service.id).all()
            supplier_ids = db.session.query(Supplier.id).order_by(Supplier.id).all()

            audit_events = []

            for (ref_model, ref_model_ids), (obj_id, audit_type, created_at, acknowledged_at) in chain(
                    izip(repeat((Service, service_ids,)), service_audit_event_params),
                    izip(repeat((Supplier, supplier_ids,)), supplier_audit_event_params),
                    ):
                ae = AuditEvent(audit_type, "henry.flower@example.com", {}, ref_model(id=ref_model_ids[obj_id]))
                ae.created_at = created_at
                ae.acknowledged_at = acknowledged_at
                ae.acknowledged = bool(acknowledged_at)
                ae.acknowledged_by = acknowledged_at and "c.p.mccoy@example.com"
                db.session.add(ae)
                audit_events.append(ae)

            db.session.commit()
            # make a note of the ids that were given to these events, or rather the order they were generated
            audit_event_id_lookup = {ae.id: i for i, ae in enumerate(audit_events)}
            assert AuditEvent.query.count() == len(service_audit_event_params)+len(supplier_audit_event_params)

            return audit_event_id_lookup


class TestAuditEvents(BaseTestAuditEvents):
    @pytest.mark.parametrize(
        "service_audit_event_params,supplier_audit_event_params,req_params,expected_resp_events",
        # where we refer to "id"s in the expected_response_params, because we can't be too sure about the *actual* ids
        # given to objects, we're using 0-based notional "ids" based on the order the audit events were inserted into
        # the db. service_audit_event_params events are inserted in the order given, followed by the
        # supplier_audit_event_params events. so if we had 5 service_audit_event_params and 2
        # supplier_audit_event_params, "5" would refer to the audit event created by the first-listed
        # supplier_audit_event_params.
        # similarly, where supplier and service "id"s are referred to, the "id"s we're referring to are normalized
        # pseudo-ids from 0-4 inclusive
        chain.from_iterable(
            ((serv_aeps, supp_aeps, req_params, expected_resp_events) for req_params, expected_resp_events in req_cases)
            for serv_aeps, supp_aeps, req_cases in (
                (
                    (   # service_audit_event_params, as consumed by add_audit_events_by_param_tuples
                        # service pseudo-id, audit type, created_at, acknowledged_at
                        (0, AuditTypes.update_service, datetime(2010, 6, 6), None,),
                        (0, AuditTypes.update_service, datetime(2010, 6, 7), None,),
                        (4, AuditTypes.update_service, datetime(2010, 6, 2), None,),
                    ),
                    (   # supplier_audit_event_params, as consumed by add_audit_events_by_param_tuples
                        # supplier pseudo-id, audit type, created_at, acknowledged_at
                        (0, AuditTypes.supplier_update, datetime(2010, 6, 6), None,),
                    ),
                    (  # and now a series of req_cases - pairs of (req_params, expected_resp_events) to test against
                       # the above db scenario. these get flattened out into concrete test scenarios by
                       # chain.from_iterable above before they reach pytest's parametrization
                        (
                            {"earliest_for_each_object": "true", "latest_first": "true"},
                            (3, 0, 2,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "latest_first": "false"},
                            (2, 0, 3,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "audit-type": "supplier_update"},
                            (3,),
                        ),
                    ),
                ),
                (
                    (   # service_audit_event_params
                        (0, AuditTypes.update_service, datetime(2011, 6, 6), None,),
                        (0, AuditTypes.update_service_status, datetime(2011, 8, 2), None,),
                        (1, AuditTypes.update_service, datetime(2011, 8, 6, 12), datetime(2011, 9, 2),),
                        (1, AuditTypes.update_service, datetime(2011, 8, 6, 9), datetime(2011, 9, 1),),
                        (0, AuditTypes.update_service, datetime(2010, 8, 4), datetime(2011, 9, 2),),
                        (3, AuditTypes.update_service, datetime(2014, 6, 6), None,),
                    ),
                    (   # supplier_audit_event_params
                        (1, AuditTypes.supplier_update, datetime(2010, 2, 6), None,),
                        (0, AuditTypes.supplier_update, datetime(2010, 6, 6), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 2, 6), None,),
                    ),
                    (   # series of req_cases for the above db scenario
                        (
                            {"earliest_for_each_object": "true"},
                            (6, 7, 4, 3, 5,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "acknowledged": "false"},
                            (6, 7, 0, 5,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "acknowledged": "true"},
                            (4, 3,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "object-type": "suppliers"},
                            (6, 7,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "audit-date": "2011-08-06"},
                            (3,),
                        ),
                        (
                            {"earliest_for_each_object": "false", "per_page": "100"},
                            (6, 8, 7, 4, 0, 1, 3, 2, 5,),
                        ),
                        (
                            {"per_page": "100"},
                            (6, 8, 7, 4, 0, 1, 3, 2, 5,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "audit-date": "2010-08-06"},
                            (),
                        ),
                    ),
                ),
                (
                    (   # service_audit_event_params
                        (0, AuditTypes.update_service, datetime(2010, 8, 5), datetime(2011, 8, 2),),
                        (0, AuditTypes.update_service, datetime(2010, 8, 4), datetime(2011, 8, 2),),
                    ),
                    (   # supplier_audit_event_params
                        (0, AuditTypes.supplier_update, datetime(2010, 6, 6), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 2, 1), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 2, 6), None,),
                        (0, AuditTypes.supplier_update, datetime(2010, 2, 7), None,),
                        (3, AuditTypes.supplier_update, datetime(2009, 1, 1), None,),
                        (0, AuditTypes.supplier_update, datetime(2010, 2, 3), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 4, 9), None,),
                        (2, AuditTypes.supplier_update, datetime(2010, 1, 1), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 8, 8), None,),
                    ),
                    (   # series of req_cases for the above db scenario
                        (
                            {"earliest_for_each_object": "true", "latest_first": "true", "per_page": "4"},
                            (1, 7, 3, 9,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "object-type": "suppliers", "latest_first": "false"},
                            (6, 9, 3, 7,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "per_page": "3", "page": "2"},
                            (7, 1,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "object-type": "suppliers", "acknowledged": "true"},
                            (),
                        ),
                    ),
                ),
                (
                    (   # service_audit_event_params
                    ),
                    (   # supplier_audit_event_params
                        (0, AuditTypes.supplier_update, datetime(2015, 3, 2), None,),
                        (3, AuditTypes.supplier_update, datetime(2015, 8, 8), None,),
                        (4, AuditTypes.supplier_update, datetime(2015, 4, 6), None,),
                        (2, AuditTypes.supplier_update, datetime(2015, 3, 3), None,),
                        (1, AuditTypes.supplier_update, datetime(2005, 8, 9), None,),
                        (1, AuditTypes.supplier_update, datetime(2015, 2, 4), None,),
                        (2, AuditTypes.supplier_update, datetime(2015, 1, 1), None,),
                        (4, AuditTypes.supplier_update, datetime(2015, 9, 3), None,),
                        (1, AuditTypes.supplier_update, datetime(2015, 4, 6), None,),
                        (1, AuditTypes.supplier_update, datetime(2015, 4, 6), None,),
                    ),
                    (   # series of req_cases for the above db scenario
                        (
                            {"earliest_for_each_object": "true", "acknowledged": "false"},
                            (4, 6, 0, 2, 1,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "audit-date": "2015-04-06"},
                            (2, 8,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "latest_first": "true", "per_page": "100"},
                            (1, 2, 0, 6, 4,),
                        ),
                        (
                            {"earliest_for_each_object": "true", "acknowledged": "true"},
                            (),
                        ),
                    ),
                ),
            )
        ),
    )
    def test_earliest_for_each_object(
            self,
            service_audit_event_params,
            supplier_audit_event_params,
            req_params,
            expected_resp_events,
            ):
        self.setup_dummy_suppliers(5)
        self.setup_dummy_services(5, supplier_id=1)
        audit_event_id_lookup = self.add_audit_events_by_param_tuples(
            service_audit_event_params,
            supplier_audit_event_params,
        )

        response = self.client.get('/audit-events?{}'.format(urlencode(req_params)))

        assert response.status_code == 200
        data = json.loads(response.get_data())

        assert tuple(audit_event_id_lookup[ae["id"]] for ae in data["auditEvents"]) == expected_resp_events

    @pytest.mark.parametrize(
        "service_audit_event_params,supplier_audit_event_params,target_audit_event_id,expected_resp_events",
        # where we refer to "id"s in the expected_response_params, because we can't be too sure about the *actual* ids
        # given to objects, we're using 0-based notional "ids" mased on the order the audit events were inserted into
        # the db. service_audit_event_params events are inserted in the order given, followed by the
        # supplier_audit_event_params events. so if we had 5 service_audit_event_params and 2
        # supplier_audit_event_params, "5" would refer to the audit event created by the first-listed
        # supplier_audit_event_params.
        # similarly, where supplier and service "id"s are referred to, the "id"s we're referring to are normalized
        # pseudo-ids from 0-4 inclusive
        chain.from_iterable(
            ((serv_aeps, supp_aeps, tgt_ae_id, expected_resp_events) for tgt_ae_id, expected_resp_events in req_cases)
            for serv_aeps, supp_aeps, req_cases in (
                (
                    (   # service_audit_event_params, as consumed by add_audit_events_by_param_tuples
                        # service pseudo-id, audit type, created_at, acknowledged_at
                        (0, AuditTypes.update_service, datetime(2010, 6, 6), None,),
                        (0, AuditTypes.update_service, datetime(2010, 6, 7), None,),
                        (4, AuditTypes.update_service, datetime(2010, 6, 2), None,),
                    ),
                    (   # supplier_audit_event_params, as consumed by add_audit_events_by_param_tuples
                        # supplier pseudo-id, audit type, created_at, acknowledged_at
                        (0, AuditTypes.supplier_update, datetime(2010, 6, 6), None,),
                    ),
                    (   # and now a series of req_cases - pairs of (tgt_ae_id, expected_resp_events) to test against
                        # the above db scenario. these get flattened out into concrete test scenarios by
                        # chain.from_iterable above before they reach pytest's parametrization
                        (
                            1,
                            frozenset((0, 1,)),
                        ),
                        (
                            2,
                            frozenset((2,)),
                        ),
                        (
                            3,
                            frozenset((3,)),
                        ),
                    ),
                ),
                (
                    (
                        (2, AuditTypes.update_service, datetime(2010, 6, 9), None,),
                        (3, AuditTypes.update_service, datetime(2010, 6, 2), None,),
                        (2, AuditTypes.update_service, datetime(2010, 6, 7), None,),
                        (2, AuditTypes.update_service, datetime(2010, 6, 1), datetime(2010, 6, 1, 1),),
                        (4, AuditTypes.update_service, datetime(2010, 6, 5), None,),
                        (2, AuditTypes.update_service_status, datetime(2010, 6, 2), None,),
                    ),
                    (
                        (0, AuditTypes.supplier_update, datetime(2010, 7, 1), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 7, 9), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 7, 8), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 7, 5), datetime(2010, 8, 1),),
                        (0, AuditTypes.supplier_update, datetime(2010, 7, 9), None,),
                        (1, AuditTypes.supplier_update, datetime(2010, 7, 1), datetime(2010, 8, 1),),
                        (1, AuditTypes.supplier_update, datetime(2010, 7, 2), datetime(2010, 8, 1),),
                        (0, AuditTypes.supplier_update, datetime(2010, 7, 6), None,),
                        (0, AuditTypes.supplier_update, datetime(2010, 7, 5), None,),
                    ),
                    (
                        (
                            0,
                            frozenset((0, 2,)),
                        ),
                        (
                            2,
                            frozenset((2,)),
                        ),
                        (
                            4,
                            frozenset((4,)),
                        ),
                        (
                            6,
                            frozenset((6,)),
                        ),
                        (
                            7,
                            frozenset((7, 8,)),
                        ),
                        (
                            10,
                            frozenset((6, 10, 13, 14,)),
                        ),
                        (
                            12,
                            frozenset(),  # already acknowledged - should have no effect
                        ),
                    ),
                ),
                (
                    (
                        (3, AuditTypes.update_service, datetime(2011, 6, 5), None,),
                        (4, AuditTypes.update_service, datetime(2011, 6, 8), None,),
                        (2, AuditTypes.update_service, datetime(2011, 6, 1), None,),
                        # note here deliberate collision of created_at and object_id to verify the secondary-ordering
                        (4, AuditTypes.update_service, datetime(2011, 6, 8), None,),
                        (4, AuditTypes.update_service_status, datetime(2011, 6, 7), datetime(2011, 6, 7, 1),),
                        (4, AuditTypes.update_service, datetime(2011, 6, 6), None,),
                        (4, AuditTypes.update_service, datetime(2011, 6, 2), datetime(2011, 8, 1),),
                    ),
                    (
                        (4, AuditTypes.supplier_update, datetime(2011, 6, 1), None,),
                        (1, AuditTypes.supplier_update, datetime(2011, 6, 9), None,),
                        (1, AuditTypes.supplier_update, datetime(2011, 6, 6), datetime(2011, 8, 1),),
                        # again here
                        (1, AuditTypes.supplier_update, datetime(2011, 6, 9), None,),
                        (3, AuditTypes.supplier_update, datetime(2011, 6, 5), None,),
                        (1, AuditTypes.supplier_update, datetime(2011, 6, 8), None,),
                    ),
                    (
                        (
                            0,
                            frozenset((0,)),
                        ),
                        (
                            1,
                            frozenset((1, 5,)),
                        ),
                        (
                            3,
                            frozenset((1, 3, 5,)),
                        ),
                        (
                            4,
                            frozenset(),  # already acknowledged - should have no effect
                        ),
                        (
                            5,
                            frozenset((5,)),
                        ),
                        (
                            6,
                            frozenset(),  # already acknowledged - should have no effect
                        ),
                        (
                            8,
                            frozenset((8, 12,)),
                        ),
                        (
                            10,
                            frozenset((8, 10, 12,)),
                        ),
                        (
                            11,
                            frozenset((11,)),
                        ),
                        (
                            12,
                            frozenset((12,)),
                        ),
                    ),
                ),
            )
        ),
    )
    def test_acknowledge_including_previous_happy_path(
            self,
            service_audit_event_params,
            supplier_audit_event_params,
            target_audit_event_id,
            expected_resp_events,
            ):
        self.setup_dummy_suppliers(5)
        self.setup_dummy_services(5, supplier_id=1)
        audit_event_id_lookup = self.add_audit_events_by_param_tuples(
            service_audit_event_params,
            supplier_audit_event_params,
        )
        audit_event_id_rlookup = {v: k for k, v in audit_event_id_lookup.items()}

        frozen_time = datetime(2016, 6, 6, 15, 32, 44, 1234)
        with freeze_time(frozen_time):
            response = self.client.post(
                "/audit-events/{}/acknowledge-including-previous".format(audit_event_id_rlookup[target_audit_event_id]),
                data=json.dumps({'updated_by': "martha.clifford@example.com"}),
                content_type='application/json',
            )

        assert response.status_code == 200
        data = json.loads(response.get_data())

        assert frozenset(audit_event_id_lookup[ae["id"]] for ae in data["auditEvents"]) == expected_resp_events

        with self.app.app_context():
            assert sorted((
                audit_event_id_lookup[id_],
                acknowledged,
                acknowledged_at,
                acknowledged_by,
            ) for id_, acknowledged, acknowledged_at, acknowledged_by in db.session.query(
                AuditEvent.id,
                AuditEvent.acknowledged,
                AuditEvent.acknowledged_at,
                AuditEvent.acknowledged_by,
            ).all()) == [
                (
                    id_,
                    (id_ in expected_resp_events) or bool(acknowledged_at),
                    (frozen_time if id_ in expected_resp_events else acknowledged_at),
                    (
                        "martha.clifford@example.com"
                        if id_ in expected_resp_events else
                        (acknowledged_at and "c.p.mccoy@example.com")
                    )
                ) for id_, (
                    obj_id,
                    audit_type,
                    created_at,
                    acknowledged_at,
                ) in enumerate(chain(service_audit_event_params, supplier_audit_event_params))
            ]

    def test_only_one_audit_event_created(self):
        with self.app.app_context():
            count = AuditEvent.query.count()
            self.add_audit_event()
            assert AuditEvent.query.count() == count + 1

    def test_should_get_audit_event(self):
        aid = self.add_audit_event(0)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())
        assert_equal(response.status_code, 200)
        expected = {
            'links': {'self': mock.ANY},
            'type': 'supplier_update',
            'acknowledged': False,
            'user': '0',
            'data': {'request': 'data'},
            'id': aid,
            'createdAt': mock.ANY
        }
        assert expected in data['auditEvents']

    def test_should_get_audit_events_sorted(self):
        self.add_audit_events(5)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(data['auditEvents'][0]['user'], '0')
        assert_equal(data['auditEvents'][4]['user'], '4')

        response = self.client.get('/audit-events?latest_first=true')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(data['auditEvents'][0]['user'], '4')
        assert_equal(data['auditEvents'][4]['user'], '0')

    def test_should_get_audit_event_using_audit_date(self):
        today = datetime.utcnow().strftime("%Y-%m-%d")

        self.add_audit_event()
        response = self.client.get('/audit-events?audit-date={}'.format(today))
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 1)
        assert_equal(data['auditEvents'][0]['user'], '0')
        assert_equal(data['auditEvents'][0]['data']['request'], 'data')

    def test_should_not_get_audit_event_for_date_with_no_events(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?audit-date=2000-01-01')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 0)

    def test_should_reject_invalid_audit_dates(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?audit-date=invalid')

        assert_equal(response.status_code, 400)

    def test_should_get_audit_event_by_type(self):
        self.add_audit_event(type=AuditTypes.contact_update)
        self.add_audit_event(type=AuditTypes.supplier_update)
        response = self.client.get('/audit-events?audit-type=contact_update')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 1)
        assert_equal(data['auditEvents'][0]['user'], '0')
        assert_equal(data['auditEvents'][0]['type'], 'contact_update')
        assert_equal(data['auditEvents'][0]['data']['request'], 'data')

    def test_should_reject_invalid_audit_type(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?audit-type=invalid')

        assert_equal(response.status_code, 400)

    def test_should_get_audit_event_by_object(self):
        self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events?object-type=suppliers&object-id=1')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 1)
        assert_equal(data['auditEvents'][0]['user'], 'rob')

    def test_should_get_audit_events_by_object_type(self):
        self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events?object-type=suppliers')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data["auditEvents"]), 3)

    def test_get_audit_event_for_missing_object_returns_404(self):
        self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events?object-type=suppliers&object-id=100000')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 404)

    def test_should_only_get_audit_event_with_correct_object_type(self):
        self.add_audit_events_with_db_object()

        with self.app.app_context():
            # Create a second AuditEvent with the same object_id but with a
            # different object_type to check that we're not filtering based
            # on object_id only
            supplier = Supplier.query.filter(Supplier.supplier_id == 1).first()
            event = AuditEvent(
                audit_type=AuditTypes.supplier_update,
                db_object=supplier,
                user='not rob',
                data={'request': "data"}
            )
            event.object_type = 'Service'

            db.session.add(event)
            db.session.commit()

        response = self.client.get('/audit-events?object-type=suppliers&object-id=1')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 1)
        assert_equal(data['auditEvents'][0]['user'], 'rob')

    def test_should_reject_invalid_object_type(self):
        self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events?object-type=invalid&object-id=1')

        assert_equal(response.status_code, 400)

    def test_should_reject_object_id_if_no_object_type_is_given(self):
        self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events?object-id=1')

        assert_equal(response.status_code, 400)

    def test_should_get_audit_events_ordered_by_created_date(self):
        self.add_audit_events(5)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 5)

        assert_equal(data['auditEvents'][4]['user'], '4')
        assert_equal(data['auditEvents'][3]['user'], '3')
        assert_equal(data['auditEvents'][2]['user'], '2')
        assert_equal(data['auditEvents'][1]['user'], '1')
        assert_equal(data['auditEvents'][0]['user'], '0')

    def test_should_reject_invalid_page(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?page=invalid')

        assert_equal(response.status_code, 400)

    def test_should_reject_missing_page(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?page=')

        assert_equal(response.status_code, 400)

    def test_should_return_404_if_page_exceeds_results(self):
        self.add_audit_events(7)
        response = self.client.get('/audit-events?page=100')

        assert_equal(response.status_code, 404)

    def test_should_get_audit_events_paginated(self):
        self.add_audit_events(7)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 5)
        next_link = data['links']['next']
        assert_in('page=2', next_link)
        assert_equal(data['auditEvents'][0]['user'], '0')
        assert_equal(data['auditEvents'][1]['user'], '1')
        assert_equal(data['auditEvents'][2]['user'], '2')
        assert_equal(data['auditEvents'][3]['user'], '3')
        assert_equal(data['auditEvents'][4]['user'], '4')

    def test_paginated_audit_events_page_two(self):
        self.add_audit_events(7)

        response = self.client.get('/audit-events?page=2')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 2)
        prev_link = data['links']['prev']
        assert_in('page=1', prev_link)
        assert_false('next' in data['links'])
        assert_equal(data['auditEvents'][0]['user'], '5')
        assert_equal(data['auditEvents'][1]['user'], '6')

    def test_paginated_audit_with_custom_page_size(self):
        self.add_audit_events(12)
        response = self.client.get('/audit-events?per_page=10')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 10)

    def test_paginated_audit_with_custom_page_size_and_specified_page(self):
        self.add_audit_events(12)
        response = self.client.get('/audit-events?page=2&per_page=10')
        data = json.loads(response.get_data())

        assert_equal(response.status_code, 200)
        assert_equal(len(data['auditEvents']), 2)
        prev_link = data['links']['prev']
        assert_in('page=1', prev_link)
        assert_false('next' in data['links'])

    def test_paginated_audit_with_invalid_custom_page_size(self):
        self.add_audit_event()
        response = self.client.get('/audit-events?per_page=foo')
        assert_equal(response.status_code, 400)

    def test_reject_invalid_audit_id_on_acknowledgement(self):
        res = self.client.post(
            '/audit-events/invalid-id!/acknowledge',
            data=json.dumps({'key': 'value'}),
            content_type='application/json')

        assert_equal(res.status_code, 404)

    def test_reject_if_no_updater_details_on_acknowledgement(self):
        res = self.client.post(
            '/audit-events/123/acknowledge',
            data={},
            content_type='application/json')

        assert_equal(res.status_code, 400)

    def test_should_update_audit_event(self):
        self.add_audit_event()
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        res = self.client.post(
            '/audit-events/{}/acknowledge'.format(
                data['auditEvents'][0]['id']
            ),
            data=json.dumps({'updated_by': 'tests'}),
            content_type='application/json')
        # re-fetch to get updated data
        new_response = self.client.get('/audit-events')
        new_data = json.loads(new_response.get_data())
        assert_equal(res.status_code, 200)
        assert_equal(new_data['auditEvents'][0]['acknowledged'], True)
        assert_equal(new_data['auditEvents'][0]['acknowledgedBy'], 'tests')

    def test_should_get_all_audit_events(self):
        self.add_audit_events(2)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        res = self.client.post(
            '/audit-events/{}/acknowledge'.format(
                data['auditEvents'][0]['id']
            ),
            data=json.dumps({'updated_by': 'tests'}),
            content_type='application/json')
        # re-fetch to get updated data
        new_response = self.client.get('/audit-events')
        new_data = json.loads(new_response.get_data())
        assert_equal(res.status_code, 200)
        assert_equal(len(new_data['auditEvents']), 2)

        # all should return both
        new_response = self.client.get('/audit-events?acknowledged=all')
        new_data = json.loads(new_response.get_data())
        assert_equal(res.status_code, 200)
        assert_equal(len(new_data['auditEvents']), 2)

    def test_should_get_only_acknowledged_audit_events(self):
        self.add_audit_events(2)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        res = self.client.post(
            '/audit-events/{}/acknowledge'.format(
                data['auditEvents'][0]['id']
            ),
            data=json.dumps({'updated_by': 'tests'}),
            content_type='application/json')
        # re-fetch to get updated data
        new_response = self.client.get(
            '/audit-events?acknowledged=true'
        )
        new_data = json.loads(new_response.get_data())
        assert_equal(res.status_code, 200)
        assert_equal(len(new_data['auditEvents']), 1)
        assert_equal(
            new_data['auditEvents'][0]['id'],
            data['auditEvents'][0]['id'])

    def test_should_get_only_not_acknowledged_audit_events(self):
        self.add_audit_events(2)
        response = self.client.get('/audit-events')
        data = json.loads(response.get_data())

        res = self.client.post(
            '/audit-events/{}/acknowledge'.format(
                data['auditEvents'][0]['id']
            ),
            data=json.dumps({'updated_by': 'tests'}),
            content_type='application/json')
        # re-fetch to get updated data
        new_response = self.client.get(
            '/audit-events?acknowledged=false'
        )
        new_data = json.loads(new_response.get_data())
        assert_equal(res.status_code, 200)
        assert_equal(len(new_data['auditEvents']), 1)
        assert_equal(
            new_data['auditEvents'][0]['id'],
            data['auditEvents'][1]['id']
        )


class TestCreateAuditEvent(BaseApplicationTest, FixtureMixin):
    @staticmethod
    def audit_event():
        audit_event = {
            "type": "register_framework_interest",
            "user": "A User",
            "data": {
                "Key": "value"
            },
        }

        return audit_event

    def audit_event_with_db_object(self):
        audit_event = self.audit_event()
        self.setup_dummy_suppliers(1)
        audit_event['objectType'] = 'suppliers'
        audit_event['objectId'] = 0

        return audit_event

    def test_create_an_audit_event(self):
        audit_event = self.audit_event()

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')

        assert_equal(res.status_code, 201)

    def test_create_an_audit_event_with_an_associated_object(self):
        audit_event = self.audit_event_with_db_object()

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')

        assert_equal(res.status_code, 201)

    def test_create_audit_event_with_no_user(self):
        audit_event = self.audit_event()
        del audit_event['user']

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')

        assert_equal(res.status_code, 201)

    def test_should_fail_if_no_type_is_given(self):
        audit_event = self.audit_event()
        del audit_event['type']

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_true(data['error'].startswith("Invalid JSON"))

    def test_should_fail_if_an_invalid_type_is_given(self):
        audit_event = self.audit_event()
        audit_event['type'] = 'invalid'

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_equal(data['error'], "invalid audit type supplied")

    def test_should_fail_if_no_data_is_given(self):
        audit_event = self.audit_event()
        del audit_event['data']

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_true(data['error'].startswith("Invalid JSON"))

    def test_should_fail_if_invalid_objectType_is_given(self):
        audit_event = self.audit_event_with_db_object()
        audit_event['objectType'] = 'invalid'

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_equal(data['error'], "invalid object type supplied")

    def test_should_fail_if_objectType_but_no_objectId_is_given(self):
        audit_event = self.audit_event_with_db_object()
        del audit_event['objectId']

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_equal(data['error'], "object type cannot be provided without an object ID")

    def test_should_fail_if_objectId_but_no_objectType_is_given(self):
        audit_event = self.audit_event_with_db_object()
        del audit_event['objectType']

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_equal(data['error'], "object ID cannot be provided without an object type")

    def test_should_fail_if_db_object_does_not_exist(self):
        audit_event = self.audit_event_with_db_object()
        audit_event['objectId'] = 6

        res = self.client.post(
            '/audit-events',
            data=json.dumps({'auditEvents': audit_event}),
            content_type='application/json')
        data = json.loads(res.get_data())

        assert_equal(res.status_code, 400)
        assert_equal(data['error'], "referenced object does not exist")


class TestGetAuditEvent(BaseTestAuditEvents):
    def test_get_existing_audit_event(self):
        event_ids = self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events/{}'.format(event_ids[0]))

        assert response.status_code == 200
        data = json.loads(response.get_data())

        assert data["auditEvents"]["id"] == event_ids[0]
        assert data["auditEvents"]["type"] == "contact_update"
        assert data["auditEvents"]["user"] == "rob"

    def test_get_nonexisting_audit_event(self):
        event_ids = self.add_audit_events_with_db_object()

        response = self.client.get('/audit-events/314159')

        assert response.status_code == 404
