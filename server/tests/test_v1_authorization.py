# Copyright (C) 2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Unit tests for Testflinger v1 API relating to job priority and
restricted queues
"""

from datetime import datetime, timedelta
import os
import base64

import jwt


def create_auth_header(client_id: str, client_key: str) -> dict:
    """
    Creates authorization header with base64 encoded client_id
    and client key using the Basic scheme
    """
    id_key_pair = f"{client_id}:{client_key}"
    base64_encoded_pair = base64.b64encode(id_key_pair.encode("utf-8")).decode(
        "utf-8"
    )
    return {"Authorization": f"Basic {base64_encoded_pair}"}


def test_retrieve_token(mongo_app_with_permissions):
    """Tests authentication endpoint which returns JWT with permissions"""
    app, _, client_id, client_key, max_priority = mongo_app_with_permissions
    output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    assert output.status_code == 200
    token = output.data
    decoded_token = jwt.decode(
        token,
        os.environ.get("JWT_SIGNING_KEY"),
        algorithms="HS256",
        options={"require": ["exp", "iat", "sub", "max_priority"]},
    )
    assert decoded_token["max_priority"] == max_priority


def test_retrieve_token_invalid_client_id(mongo_app_with_permissions):
    """
    Tests that authentication endpoint returns 401 error code
    when receiving invalid client key
    """
    app, _, _, client_key, _ = mongo_app_with_permissions
    client_id = "my_wrong_id"
    output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    assert output.status_code == 401


def test_retrieve_token_invalid_client_key(mongo_app_with_permissions):
    """
    Tests that authentication endpoint returns 401 error code
    when receiving invalid client key
    """
    app, _, client_id, _, _ = mongo_app_with_permissions
    client_key = "my_wrong_key"
    output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    assert output.status_code == 401


def test_job_with_priority(mongo_app_with_permissions):
    """Tests submission of priority job with valid token"""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    job = {"job_queue": "myqueue2", "job_priority": 200}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 200 == job_response.status_code


def test_star_priority(mongo_app_with_permissions):
    """
    Tests submission of priority job for a generic queue
    with star priority permissions
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    job = {"job_queue": "mygenericqueue", "job_priority": 1}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 200 == job_response.status_code


def test_priority_no_token(mongo_app_with_permissions):
    """Tests rejection of priority job with no token"""
    app, _, _, _, _ = mongo_app_with_permissions
    job = {"job_queue": "myqueue2", "job_priority": 200}
    job_response = app.post("/v1/job", json=job)
    assert 401 == job_response.status_code


def test_priority_invalid_queue(mongo_app_with_permissions):
    """Tests rejection of priority job with invalid queue"""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    job = {"job_queue": "myinvalidqueue", "job_priority": 200}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 403 == job_response.status_code


def test_priority_expired_token(mongo_app_with_permissions):
    """Tests rejection of priority job with expired token"""
    app, _, _, _, _ = mongo_app_with_permissions
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    expired_token_payload = {
        "exp": datetime.utcnow() - timedelta(seconds=2),
        "iat": datetime.utcnow() - timedelta(seconds=4),
        "sub": "access_token",
        "max_priority": {},
    }
    token = jwt.encode(expired_token_payload, secret_key, algorithm="HS256")
    job = {"job_queue": "myqueue", "job_priority": 100}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 403 == job_response.status_code
    assert "Token has expired" in job_response.text


def test_missing_fields_in_token(mongo_app_with_permissions):
    """Tests rejection of priority job with token with missing fields"""
    app, _, _, _, _ = mongo_app_with_permissions
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    incomplete_token_payload = {
        "max_priority": {},
    }
    token = jwt.encode(incomplete_token_payload, secret_key, algorithm="HS256")
    job = {"job_queue": "myqueue", "job_priority": 100}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 403 == job_response.status_code
    assert "Invalid Token" in job_response.text


def test_job_get_with_priority(mongo_app_with_permissions):
    """Tests job get returns job with highest job priority"""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    jobs = [
        {"job_queue": "myqueue2"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue2", "job_priority": 100},
    ]
    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)
    returned_job_ids = []
    for _ in range(len(jobs)):
        job_get_response = app.get("/v1/job?queue=myqueue2")
        job_id = job_get_response.json.get("job_id")
        returned_job_ids.append(job_id)
    assert returned_job_ids[0] == job_ids[1]
    assert returned_job_ids[1] == job_ids[2]
    assert returned_job_ids[2] == job_ids[0]


def test_job_get_with_priority_multiple_queues(mongo_app_with_permissions):
    """
    Tests job get returns job with highest job priority when jobs are
    submitted across different queues
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    jobs = [
        {"job_queue": "myqueue3"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue", "job_priority": 100},
    ]
    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)
    returned_job_ids = []
    for _ in range(len(jobs)):
        job_get_response = app.get(
            "/v1/job?queue=myqueue&queue=myqueue2&queue=myqueue3"
        )
        job_id = job_get_response.json.get("job_id")
        returned_job_ids.append(job_id)
    assert returned_job_ids[0] == job_ids[1]
    assert returned_job_ids[1] == job_ids[2]
    assert returned_job_ids[2] == job_ids[0]


def test_job_position_get_with_priority(mongo_app_with_permissions):
    """Tests job position get returns correct position with priority"""
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    jobs = [
        {"job_queue": "myqueue2"},
        {"job_queue": "myqueue2", "job_priority": 200},
        {"job_queue": "myqueue2", "job_priority": 100},
    ]
    job_ids = []
    for job in jobs:
        job_response = app.post(
            "/v1/job", json=job, headers={"Authorization": token}
        )
        job_id = job_response.json.get("job_id")
        job_ids.append(job_id)

    job_positions = []
    for job_id in job_ids:
        job_positions.append(app.get(f"/v1/job/{job_id}/position").text)

    assert job_positions[0] == "2"
    assert job_positions[1] == "0"
    assert job_positions[2] == "1"


def test_restricted_queue_allowed(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are accepted
    when the token allows that queue
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    # rqueue1 is a restricted queue that is allowed for this client
    job = {"job_queue": "rqueue1"}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 200 == job_response.status_code


def test_restricted_queue_reject(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are rejected
    when the client is not allowed
    """
    app, _, client_id, client_key, _ = mongo_app_with_permissions
    authenticate_output = app.post(
        "/v1/oauth2/token",
        headers=create_auth_header(client_id, client_key),
    )
    token = authenticate_output.data.decode("utf-8")
    # rqueue3 is a restricted queue that is not allowed for this client
    job = {"job_queue": "rqueue3"}
    job_response = app.post(
        "/v1/job", json=job, headers={"Authorization": token}
    )
    assert 403 == job_response.status_code


def test_restricted_queue_reject_no_token(mongo_app_with_permissions):
    """
    Tests that jobs that submit to a restricted queue are rejected
    when no token is included
    """
    app, _, _, _, _ = mongo_app_with_permissions
    job = {"job_queue": "rqueue1"}
    job_response = app.post("/v1/job", json=job)
    assert 401 == job_response.status_code