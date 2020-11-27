from flask import Blueprint, request, current_app, url_for, g
from pymongo.errors import DuplicateKeyError
from datetime import datetime
from passlib.hash import sha256_crypt
from flaskr.domain.documents.User import User
from flaskr.domain.repositories.UserRepository import UserRepository 
from flaskr.domain.repositories.RefreshTokenRepository import RefreshTokenRepository 
from flaskr.domain.mongo import getDb, DbClient
from flaskr.formatters.UserFormatter import forApiAsDict
from flaskr.services import AuthService, RequestService, EmailService

import logging
logger = logging.getLogger( __name__ )

controller = Blueprint('user', __name__, url_prefix='/user')

@controller.route("", methods=['POST'])
@RequestService.validate(kind='user_create')
def create():
    content = request.get_json(silent=True)
    if content == None:
        return {'message': 'Invalid request'}, 400

    user = User(content)
    try:
        user.setCreate(datetime.utcnow())
        user.setActive(False)
        password = sha256_crypt.hash(content.get('password'))
        user.setPassword(password)
        repo = UserRepository(getDb())
        repo.add(user)

        emailService = EmailService.getEmailService()

        activationUrl = current_app.config['BASE_URL'] + url_for(
            'user.activate', 
            username=user.username, 
            code=user.activationCode
        )

        contents = emailService.prepareContents(
            'activation', 
            user.locale, 
            username=user.username,
            publicName=user.publicName,
            url=activationUrl
        )   
        #TODO offline!!   
        emailService.sendEmail(user.publicName, user.email, contents)

    except DuplicateKeyError as e:
        keyColumn = list(e.details.get('keyPattern').keys())[0]
        if keyColumn == 'username':
            return {'message': 'Please choose different username'}, 400
        elif keyColumn == 'email':
            return {'message': 'You cannot use this email address'}, 400
        else:
            raise Exception('Unknown column key raised error : "'+keyColumn+'"')
        return {'message': 'User already exists! - this error should not be here'}, 400

    return '', 204

@controller.route("", methods=['PATCH'])
@controller.route("/<username>", methods=['PATCH'])
@AuthService.is_logged()
@RequestService.validate(kind='user_update')
def update(username: str = None):
    repo = UserRepository(getDb())
    if username == None:
        user = g.user
    elif g.user.hasRole('ADMIN') and username != None:
        user = repo.findByUsername(username)
        if user == None:
            return {'message': 'User not found'}, 400
    else:
        return {'message': 'Not allowed'}, 403

    content = request.get_json(silent=True)
    if content == None:
        return {'message': 'Validation failed'}, 400

    try:
        if content.get('password'):
            content['password'] = sha256_crypt.hash(content.get('password'))
        
        hasNewEmail = False
        if content.get('email') and user.email != content.get('email'):
            user.setActive(False)
            hasNewEmail = True

        for key, value in content.items():
            setattr(user, key, value)

        repo.update(user)
        if hasNewEmail:
            return {'message': 'Please activate your email'}, 200
        else:
            return '', 204
    except DuplicateKeyError as e:
        keyColumn = list(e.details.get('keyPattern').keys())[0]
        if keyColumn == 'username':
            return {'message': 'Please choose different username'}, 400
        elif keyColumn == 'email':
            return {'message': 'You cannot use this email address'}, 400
        else:
            raise Exception('Unknown column key raised error : "'+keyColumn+'"')
        return {'message': 'User already exists! - this error should not be here'}, 400
    return '', 204

@controller.route("/<username>/activate/<code>", methods=['PATCH'])
def activate(username, code):
    repo = UserRepository(getDb())
    user = repo.findByUsername(username)
    if user == None:
        return {'message': 'Wrong username'}, 400

    if user.activationCode != code:
        return {'message': 'Wrong activation code'}, 400

    user.setActive(True)

    repo.update(user)

    return '', 204

@controller.route("", methods=['GET'], endpoint='get')
@controller.route("/<username>", methods=['GET'], endpoint='get')
@AuthService.is_logged()
def getUser(username: str = None):
    if username == None:
        return {'data': g.user.toDictResponse()}, 200
    elif g.user.hasRole('ADMIN') and username != None:
        repo = UserRepository(getDb())
        user = repo.findByUsername(username)
        if user:
            return {'data': user.toDictResponse()}, 200
        else:
            return {'message': 'User does not exists'}, 400
    else:
        return {'message': 'Not allowed'}, 403

@controller.route("", methods=['DELETE'])
@controller.route("/<username>", methods=['DELETE'])
@AuthService.is_logged()
def deleteUser(username: str = None):
    repo = UserRepository(getDb())
    if username == None:
        user = g.user
    elif g.user.hasRole('ADMIN') and username != None:
        user = repo.findByUsername(username)
        if user == None:
            return {'message': 'User not found'}, 400
    else:
        return {'message': 'Not allowed'}, 403
    repoRT = RefreshTokenRepository(getDb())
    try:
        repo.delete(user.id)
        repoRT.deleteForUser(user)
    except Exception as e:
        current_app.logger.error(e)
        return {'message': 'Error during deletion'}, 500
    return '', 204