from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
import isel.services.users as users_svc
import isel.services.audit as audit_svc
from isel.utils.admin_auth import admin_required
from isel.utils.image import decode_image

bp = Blueprint('users', __name__)


@bp.get('/api/users')
def get_users():
    return jsonify(users_svc.get_all_users_info())


@bp.get('/api/user/<int:user_id>/profile')
def get_user_profile(user_id: int):
    from isel.services.stats import get_user_profile
    data = get_user_profile(user_id)
    if data is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(data)


@bp.post('/api/register')
@admin_required
def register():
    data = request.json
    name = data['name'].strip()
    user_type = data.get('user_type', '学生')

    if not name:
        return jsonify({'success': False, 'message': '名前を入力してください'})
    if users_svc.user_name_exists(name):
        return jsonify({'success': False, 'message': f'「{name}」は既に登録されています'})

    engine = current_app.config['FACE_ENGINE']
    frame = decode_image(data['image'])
    embedding = engine.extract_embedding(frame, enforce=True)
    if embedding is None:
        return jsonify({'success': False, 'message': '顔を検出できませんでした'})

    dup_id, dup_name, _ = engine.find_match(embedding, engine.reg_threshold)
    if dup_id is not None:
        return jsonify({'success': False, 'message': f'この方は既に「{dup_name}」として登録されています'})

    new_user_id = users_svc.register_user(name, user_type, embedding)
    audit_svc.record('REGISTER', new_user_id, name)
    return jsonify({'success': True, 'message': f'{name}さんを登録しました', 'user_id': new_user_id})


@bp.delete('/api/user/<int:user_id>')
@admin_required
def delete_user(user_id: int):
    try:
        name = users_svc.get_user_name(user_id)
        users_svc.delete_user(user_id)
        audit_svc.record('DELETE', user_id, name or f'user_{user_id}')
        return jsonify({'success': True, 'message': 'ユーザーを削除しました'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.put('/api/user/<int:user_id>')
@admin_required
def update_user(user_id: int):
    data = request.json
    name = data.get('name', '').strip()
    user_type = data.get('user_type', '').strip()
    if not name or not user_type:
        return jsonify({'success': False, 'message': 'name and user_type required'}), 400
    result = users_svc.update_user(user_id, name, user_type)
    return jsonify(result), (200 if result['success'] else 400)


@bp.post('/api/user/<int:user_id>/face')
@admin_required
def update_user_face(user_id: int):
    engine = current_app.config['FACE_ENGINE']
    frame = decode_image(request.json['image'])
    emb = engine.extract_embedding(frame, enforce=True)
    if emb is None:
        return jsonify({'success': False, 'message': 'No face detected in image'}), 400
    emb_list = [float(v) for v in emb]
    result = users_svc.update_face(user_id, emb_list)
    return jsonify(result), (200 if result['success'] else 400)
