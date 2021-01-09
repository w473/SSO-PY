from flaskr.domain.documents.User import User
from flaskr.services.JwtService import encodeJwt
from flaskr.services.RequestService import getRequest
from flask import current_app


def findUser(email: str, params: dict) -> User:
    payload = {
        'username': 'sso',
        'roles': ['SYSTEM', 'ADMIN']
    }

    token = encodeJwt(payload)

    url = current_app.config['USERS_SERVICE_URL'] + '/fetchByEmail/' + email

    payload = {}
    if 'password' in params:
        payload['password'] = params['password']
        url += "/1"
    elif len(params) != 0:
        raise Exception('Not implemented')

    headers = {'Authorization': 'Bearer ' + token}

    r = getRequest().post(url, payload, headers)

    response = r.json()
    if r.status_code in [400, 403]:
        return None
    if r.status_code != 200:
        raise Exception(response['message'])

    return User(response.get('payload'))
