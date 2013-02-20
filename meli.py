# -*- coding: utf-8 -*-

import json
import requests
from urllib import urlencode

import sys
import logging
from decimal import Decimal
import datetime

logging.basicConfig(filename='meli.log', level=logging.INFO)
logging.getLogger('django').setLevel(logging.ERROR)


# Errors...
class ValidationError(Exception):
    pass


class GenericError(Exception):
    pass


class NotAllowed(Exception):
    pass


class InternalError(Exception):
    pass


class InvalidGrant(Exception):
    pass


class Forbidden(Exception):
    pass


class InvalidPostBody(Exception):
    pass


class Meli(object):

    access_token = None
    app_id = None
    app_secret = None
    base_url = 'https://api.mercadolibre.com'
    status_code = None
    success_status = [200, 201, 202, 204]
    refresh_token = None
    expires = None

    def __init__(self, app_id=None, app_secret=None, access_token=None):

        logging.info('initiating meli...')
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = access_token

    def __nonzero__(self):

        if self.status_code not in self.success_status:
            logging.info('Status code (%s): HTTP' % self.status_code)
            return False
        return True

    def json_handler(self, data):
        # convert decimal to float
        # and datetime to isoformat :)
        json_output = {}
        for k, v in data.items():
            if isinstance(v, Decimal):
                json_output[k] = float(v)
            elif isinstance(v, datetime.datetime):
                json_output[k] = v.isoformat()
            else:
                json_output[k] = v
        return json.dumps(json_output)

    def make_request(self, method='GET', path=None, data=None, **params):
        # cleaning stuff
        self.data = {}

        url = self.compose_url(path, **params)
        if method == 'GET':
            self.data = self.parse_response(requests.get(url))
        elif method == 'POST':
            if isinstance(data, dict) or isinstance(data, list):
                try:
                    data = self.json_handler(data)
                except Exception as e:
                    logging.error('Invalid data? (%s)' % e.message)
                    return self
            self.data = self.parse_response(requests.post(url, data=data))
        elif method == 'PUT':
            if isinstance(data, dict) or isinstance(data, list):
                try:
                    data = self.json_handler(data)
                except Exception as e:
                    logging.error('Invalid data? (%s)' % e.message)
                    return self
            self.data = self.parse_response(requests.put(url, data=data))
        elif method == 'OPTIONS':
            return self.show_help(self.parse_response(requests.options(url)))
        elif method == 'DELETE':
            self.data = self.parse_response(requests.delete(url))
        else:
            logging.info('not yet supported')
        return self

    def compose_url(self, path, **params):
        if not path.startswith('/'):
            path = "/%s" % path
        if params:
            if 'access' in params:
                if self.get_access_token():
                    params['access_token'] = self.get_access_token()
                else:
                    logging.warn('Empty or invalid access_token')
                params.pop('access')
            # joining the lists with ,
            for k, v in params.items():
                if isinstance(v, list):
                    params[k] = ','.join(v)
            url = self.base_url + path + '?' + urlencode(params)
        else:
            url = self.base_url + path

        logging.info("URL: %s" % url)
        return url

    def get(self, path, **params):
        return self.make_request('GET', path, **params)

    def post(self, path, data=None, **params):
        return self.make_request('POST', path, data, **params)

    def put(self, path, data, **params):
        return self.make_request('PUT', path, data, **params)

    def delete(self, path, **params):
        return self.make_request('DELETE', path, **params)

    def help(self, path, **params):
        return self.make_request('OPTIONS', path, **params)

    def get_access_token(self, code=None, redirect_uri=None):
        if code and redirect_uri:
            access_token = self.post('oauth/token', grant_type='authorization_code', client_id=self.app_id, client_secret=self.app_secret, code=code, redirect_uri=redirect_uri)

            if 'access_token' in access_token.data.keys():
                self.access_token = access_token.data.get('access_token')
                self.refresh_token = access_token.data.get('refresh_token')
                self.expires = access_token.data.get('expires_in')
            else:
                self.access_token = None
        if self.access_token:
            return self.access_token

    def refresh_access_token(self, refresh_token=None):
        if refresh_token:
            resposta = self.post('oauth/token', {}, grant_type='refresh_token', client_id=self.app_id, client_secret=self.app_secret, refresh_token=refresh_token)
            if 'access_token' in resposta.data:
                self.access_token = resposta.data.get('access_token')
                self.expires = resposta.data.get('expires_in')
                self.refresh_token = resposta.data.get('refresh_token')
                return self.access_token
        return None

    def set_access_token(self, token):
        self.access_token = token

    def parser_error(self, data):
        if not data:
            logging.info('Data is empty')
            return None
        if not self:
            logging.info('Yeah, we have a error!')
            name = self.parse_exception_name(data.get('error', 'generic_error'))
            causes = ''
            if data.get('cause'):
                logging.error(data.get('cause'))
                for i in data.get('cause', []):
                    try:
                        causes += ' %s\n' % i.get('message', '')
                    except:
                        causes += ' %s\n' % i

            else:
                causes = data.get('message')
            try:
                ex = getattr(sys.modules[__name__], name)(causes)
            except AttributeError:
                logging.warn('Exception %s not found, expected?' % name)
                return None
            raise ex

    def parse_exception_name(self, name):
        normalize_name = ''
        for i in name.split('_'):
            normalize_name += i.title()
        return normalize_name

    def parse_response(self, response):
        try:
            data = json.loads(response.text)
            # get the status from mercadolibre status code.
            logging.info('We got a json file!')

        except:
            # not json
            data = {
                'status': response.status_code,
                'data': response.text
            }

        self.status_code = response.status_code
        # raise error?
        self.parser_error(data)

        return data

    def get_login_url(self, redirect_uri=None):

        base_url = 'https://auth.mercadolivre.com.br/authorization'
        params = {
            'response_type': 'code',
            'client_id': self.app_id,
            'redirect_uri': redirect_uri
        }
        return base_url + '?' + urlencode(params)

    def show_help(self, data):
        attributes = ', '.join([k for k in data.get('attributes', {}).keys()])
        methods = ''
        for i in data.get('methods'):
            methods += '    %s: (%s) %s\n' % (i.get('method'), i.get('example'), i.get('description'))

        print """
        ---- %s

        %s

        Attributes:
        %s

        Methods:
        %s
        """ % (data.get('name'), data.get('description'), attributes, methods)
