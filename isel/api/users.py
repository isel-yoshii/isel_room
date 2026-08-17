from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
import isel.services.users as users_svc
import isel.services.audit as audit_svc
from isel.services.users import VARIANT_KEYS
from isel.utils import admin_required, ok, fail

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
        return fail('名前を入力してください')
    if users_svc.user_name_exists(name):
        return fail(f'「{name}」は既に登録されています')

    engine = current_app.config['FACE_ENGINE']
    variants_b64 = data.get('variants') or {}

    variants_emb: dict[str, list[list[float]]] = {}
    for key, b64_list in variants_b64.items():
        if key not in VARIANT_KEYS or not b64_list:
            continue
        embs = engine.embeddings_from_frames(b64_list, limit=3)
        if embs:
            variants_emb[key] = embs

    if 'normal' not in variants_emb:
        return fail('顔を検出できませんでした (normal variant required)')

    dup_id, dup_name, _ = engine.find_match(variants_emb['normal'][0], engine.reg_threshold)
    if dup_id is not None:
        return fail(f'この方は既に「{dup_name}」として登録されています')

    new_user_id = users_svc.register_user(name, user_type, variants_emb)
    audit_svc.record('REGISTER', new_user_id, name)
    return ok(
        message=f'{name}さんを登録しました ({", ".join(variants_emb.keys())})',
        user_id=new_user_id,
        variants=list(variants_emb.keys()),
    )


@bp.delete('/api/user/<int:user_id>')
@admin_required
def delete_user(user_id: int):
    name = users_svc.get_user_name(user_id)
    users_svc.delete_user(user_id)
    audit_svc.record('DELETE', user_id, name or f'user_{user_id}')
    return ok('ユーザーを削除しました')


@bp.put('/api/user/<int:user_id>')
@admin_required
def update_user(user_id: int):
    data = request.json
    name = data.get('name', '').strip()
    user_type = data.get('user_type', '').strip()
    if not name or not user_type:
        return fail('name and user_type required')
    users_svc.update_user(user_id, name, user_type)
    return ok()


@bp.post('/api/user/<int:user_id>/face')
@admin_required
def set_user_face_variant(user_id: int):
    engine = current_app.config['FACE_ENGINE']
    data = request.json or {}
    variant = data.get('variant')
    if variant not in VARIANT_KEYS:
        return fail('Invalid variant')
    frames_emb = engine.embeddings_from_frames(data.get('images') or [], limit=3)
    if not frames_emb:
        return fail('No face detected in any frame')
    variants = users_svc.set_face_variant(user_id, variant, frames_emb)
    return ok(variants=variants)
