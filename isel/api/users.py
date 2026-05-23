from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
import isel.services.users as users_svc
import isel.services.audit as audit_svc
from isel.services.users import VARIANT_KEYS
from isel.utils import admin_required
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
    variants_b64 = data.get('variants')
    if variants_b64 is None:
        # Backward-compat: prior `images` / `image` payloads → treat as 'normal'.
        legacy = data.get('images') or ([data['image']] if data.get('image') else [])
        variants_b64 = {'normal': legacy} if legacy else {}

    variants_emb: dict[str, list[list[float]]] = {}
    for key, b64_list in variants_b64.items():
        if key not in VARIANT_KEYS or not b64_list:
            continue
        embs = []
        for b64 in b64_list[:3]:
            frame = decode_image(b64)
            emb = engine.extract_embedding(frame, enforce=True)
            if emb is not None:
                embs.append([float(v) for v in emb])
        if embs:
            variants_emb[key] = embs

    if 'normal' not in variants_emb:
        return jsonify({'success': False, 'message': '顔を検出できませんでした (normal variant required)'})

    dup_id, dup_name, _ = engine.find_match(variants_emb['normal'][0], engine.reg_threshold)
    if dup_id is not None:
        return jsonify({'success': False, 'message': f'この方は既に「{dup_name}」として登録されています'})

    new_user_id = users_svc.register_user(name, user_type, variants_emb)
    audit_svc.record('REGISTER', new_user_id, name)
    return jsonify({
        'success': True,
        'message': f'{name}さんを登録しました ({", ".join(variants_emb.keys())})',
        'user_id': new_user_id,
        'variants': list(variants_emb.keys()),
    })


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
def set_user_face_variant(user_id: int):
    engine = current_app.config['FACE_ENGINE']
    data = request.json or {}
    variant = data.get('variant')
    if variant not in VARIANT_KEYS:
        return jsonify({'success': False, 'message': 'Invalid variant'}), 400
    frames_b64 = data.get('images') or ([data['image']] if data.get('image') else [])
    frames_emb = []
    for b64 in frames_b64[:3]:
        frame = decode_image(b64)
        emb = engine.extract_embedding(frame, enforce=True)
        if emb is not None:
            frames_emb.append([float(v) for v in emb])
    if not frames_emb:
        return jsonify({'success': False, 'message': 'No face detected in any frame'}), 400
    result = users_svc.set_face_variant(user_id, variant, frames_emb)
    return jsonify(result), (200 if result['success'] else 400)
