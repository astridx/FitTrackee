from flask import Blueprint, jsonify, send_file

from .models import User

users_blueprint = Blueprint('users', __name__)


@users_blueprint.route('/users', methods=['GET'])
def get_users():
    """Get all users"""
    users = User.query.all()
    response_object = {
        'status': 'success',
        'data': {
            'users': [user.serialize() for user in users]
        }
    }
    return jsonify(response_object), 200


@users_blueprint.route('/users/<user_id>', methods=['GET'])
def get_single_user(user_id):
    """Get single user details"""
    response_object = {
        'status': 'fail',
        'message': 'User does not exist'
    }
    try:
        user = User.query.filter_by(id=int(user_id)).first()
        if not user:
            return jsonify(response_object), 404
        else:
            response_object = {
                'status': 'success',
                'data': user.serialize()
            }
            return jsonify(response_object), 200
    except ValueError:
        return jsonify(response_object), 404


@users_blueprint.route('/users/<user_id>/picture', methods=['GET'])
def get_picture(user_id):
    response_object = {
        'status': 'fail',
        'message': 'User does not exist'
    }
    try:
        user = User.query.filter_by(id=int(user_id)).first()
        if not user:
            return jsonify(response_object), 404
        else:
            return send_file(user.picture)
    except ValueError:
        return jsonify(response_object), 404


@users_blueprint.route('/ping', methods=['GET'])
def ping_pong():
    return jsonify({
        'status': 'success',
        'message': 'pong!'
    })