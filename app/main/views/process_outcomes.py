import datetime

from flask import abort
from dmapiclient.audit import AuditTypes

from .. import main
from ... import db
from ...models import AuditEvent, ProcessOutcome

from ...utils import (
    get_json_from_request,
    json_has_required_keys,
    single_result_response,
    validate_and_return_updater_request,
)
from ...validation import validate_process_outcome_json_or_400


@main.route("/process-outcomes/<int:process_outcome_id>", methods=("GET",))
def get_process_outcome(process_outcome_id):
    process_outcome = ProcessOutcome.query.filter_by(external_id=process_outcome_id).first_or_404()

    return single_result_response("processOutcome", process_outcome), 200


@main.route("/process-outcomes/<int:process_outcome_id>", methods=("PUT",))
def update_process_outcome(process_outcome_id):
    uniform_now = datetime.datetime.utcnow()

    updater_json = validate_and_return_updater_request()

    json_payload = get_json_from_request()
    json_has_required_keys(json_payload, ["processOutcome"])
    process_outcome_json = json_payload["processOutcome"]

    validate_process_outcome_json_or_400(process_outcome_json)

    # fetch and lock ProcessOutcome row so we know writing this back won't overwrite any other updates to it that made
    # it in in the meantime
    process_outcome = db.session.query(ProcessOutcome).filter_by(
        external_id=process_outcome_id,
    ).with_for_update().first()

    if not process_outcome:
        abort(404, f"Process outcome {process_outcome_id} not found")

    process_outcome.update_from_json(process_outcome_json)

    if process_outcome.completed_at is not None and process_outcome_json.get("completed") is False:
        abort(400, f"Can't un-complete process outcome")
    if process_outcome.completed_at is None and process_outcome_json.get("completed") is True:
        # make a cursory check for existing ProcessOutcome collisions. we're not actually totally relying on this
        # to police the constraint - there is a database unique constraint that will do that for us in a transactionally
        # bulletproof way. we do this check here manually too to be able to give a nicer error message in the 99% case.
        if process_outcome.brief and process_outcome.brief.process_outcome:
            abort(400, "Brief {} already has a complete process outcome: {}".format(
                process_outcome.brief_id,
                process_outcome.brief.process_outcome.external_id,
            ))
        if process_outcome.direct_award_project and process_outcome.direct_award_project.process_outcome:
            abort(400, "Direct award project {} already has a complete process outcome: {}".format(
                process_outcome.direct_award_project_id,
                process_outcome.direct_award_project.process_outcome.external_id,
            ))

        process_outcome.completed_at = uniform_now
        complete_audit_event = AuditEvent(
            audit_type=AuditTypes.complete_process_outcome,
            user=updater_json['updated_by'],
            db_object=process_outcome,
            data={},
        )
        complete_audit_event.created_at = uniform_now
        db.session.add(complete_audit_event)

    update_audit_event = AuditEvent(
        audit_type=AuditTypes.update_process_outcome,
        user=updater_json['updated_by'],
        db_object=process_outcome,
        data=process_outcome_json,
    )
    update_audit_event.created_at = uniform_now
    db.session.add(update_audit_event)
    db.session.commit()

    return single_result_response("processOutcome", process_outcome), 200
