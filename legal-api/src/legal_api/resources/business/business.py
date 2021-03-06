# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Searching on a business entity.

Provides all the search and retrieval from the business entity datastore.
"""
from contextlib import suppress
from http import HTTPStatus

from flask import jsonify, request
from flask_babel import _ as babel  # noqa: N813
from flask_restplus import Resource, cors

from legal_api.models import Business, Filing, RegistrationBootstrap
from legal_api.resources.business.business_filings import ListFilingResource
from legal_api.services import RegistrationBootstrapService
from legal_api.utils.auth import jwt
from legal_api.utils.util import cors_preflight

from .api_namespace import API


@cors_preflight('GET, POST')
@API.route('/<string:identifier>', methods=['GET', 'OPTIONS'])
@API.route('', methods=['POST', 'OPTIONS'])
class BusinessResource(Resource):
    """Meta information about the overall service."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @jwt.requires_auth
    def get(identifier: str):
        """Return a JSON object with meta information about the Service."""
        # check authorization
        # if not authorized(identifier, jwt, action=['view']):
        #     return jsonify({'message':
        #                     f'You are not authorized to view business {identifier}.'}), \
        #         HTTPStatus.UNAUTHORIZED

        if identifier.startswith('T'):
            return {'message': babel('No information on temp registrations.')}, 200

        business = Business.find_by_identifier(identifier)

        if not business:
            return jsonify({'message': f'{identifier} not found'}), HTTPStatus.NOT_FOUND

        return jsonify(business=business.json())

    @staticmethod
    @cors.crossdomain(origin='*')
    @jwt.requires_auth
    def post():
        """Create an Incorporation Filing, else error out."""
        json_input = request.get_json()

        try:
            filing_account_id = json_input['filing']['header']['accountId']
            filing_type = json_input['filing']['header']['name']
            if filing_type != Filing.FILINGS['incorporationApplication']['name']:
                raise TypeError
        except (TypeError, KeyError):
            return {'error': babel('Requires a minimal Incorporation Filing.')}, HTTPStatus.BAD_REQUEST

        # @TODO rollback bootstrap if there is A failure, awaiting changes in the affiliation service
        bootstrap = RegistrationBootstrapService.create_bootstrap(filing_account_id)
        if not isinstance(bootstrap, RegistrationBootstrap):
            return {'error': babel('Unable to create Incorporation Filing.')}, HTTPStatus.SERVICE_UNAVAILABLE

        try:
            business_name = json_input['filing']['incorporationApplication']['nameRequest']['nrNumber']
        except KeyError:
            business_name = bootstrap.identifier
        rv = RegistrationBootstrapService.register_bootstrap(bootstrap, business_name)
        if not isinstance(rv, HTTPStatus):
            with suppress(Exception):
                bootstrap.delete()
            return {'error': babel('Unable to create Incorporation Filing.')}, HTTPStatus.SERVICE_UNAVAILABLE

        return ListFilingResource.put(bootstrap.identifier, None)
