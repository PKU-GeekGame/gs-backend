from flask_admin.contrib import sqla, fileadmin
from flask_admin.form import SecureForm
from flask_admin.babel import lazy_gettext
from flask_admin.actions import action
from flask_admin.model.template import macro
from flask_admin import AdminIndexView, expose
from wtforms import validators, Form
from sqlalchemy import select
from markupsafe import Markup
from flask import current_app, flash, redirect, url_for, make_response, request
import asyncio
import json
import time
from flask.typing import ResponseReturnValue
from typing import Any, Optional, Type, Dict, List

from ..state import Trigger
from . import fields
from ..logic import glitter
from ..logic.reducer import Reducer
from .. import store
from .. import utils

class StatusView(AdminIndexView):  # type: ignore
    @expose('/')
    def index(self) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        reducer.received_telemetries[reducer.process_name] = (time.time(), reducer.collect_telemetry())

        USER_STATUS = {
            'total': '总数',
            'disabled': '已禁用',
            'pending_terms': '未同意条款',
            'pending_profile': '未完善信息',
            'no_score': '无成绩',
            'have_score': '有成绩',
        }

        TELEMETRY_FIELDS = {
            'last_update': '更新时间',
            'ws_online_clients': '在线连接',
            'ws_online_uids': '在线用户',
            'state_counter': '状态编号',
            'game_available': '比赛可用',
            'cur_tick': 'Tick',
            'n_users': '用户数',
            'n_submissions': '提交数',
        }

        st = utils.sys_status()
        sys_status = {
            'process': f'{st["process"]}',
            'load': f'{st["load_1"]} {st["load_5"]} {st["load_15"]}',
            'ram': f'used={st["ram_used"]:.2f}G, free={st["ram_free"]:.2f}G',
            'swap': f'used={st["swap_used"]:.2f}G, free={st["swap_free"]:.2f}G',
            'disk': f'used={st["disk_used"]:.2f}G, free={st["disk_free"]:.2f}G',
        }

        users_cnt_by_group: Dict[str, Dict[str, int]] = {}

        for u in reducer._game.users.list:
            u_group = u._store.group

            if not u._store.enabled:
                u_status = 'disabled'
            elif not u._store.terms_agreed:
                u_status = 'pending_terms'
            elif u._store.profile.check_profile(u._store.group) is not None:
                u_status = 'pending_profile'
            elif u.tot_score==0:
                u_status = 'no_score'
            else:
                u_status = 'have_score'

            users_cnt_by_group.setdefault(u_group, {}).setdefault(u_status, 0)
            users_cnt_by_group.setdefault(u_group, {}).setdefault('total', 0)
            users_cnt_by_group[u_group][u_status] += 1
            users_cnt_by_group[u_group]['total'] += 1

        return self.render(
            'status.html',

            sys_status=sys_status,

            user_fields=USER_STATUS,
            user_data=users_cnt_by_group,

            tel_fields=TELEMETRY_FIELDS,
            tel_data={
                worker_name: {
                    'last_update': f'{int(time.time()-last_update):d}s',
                    **tel_dict,
                } for worker_name, (last_update, tel_dict) in sorted(reducer.received_telemetries.items())
            },
        )

    @expose('/clear_telemetry')
    def clear_telemetry(self) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        reducer.received_telemetries.clear()

        flash('已清空遥测数据', 'success')
        return redirect(url_for('.index'))

    @expose('/test_push')
    def test_push(self) -> ResponseReturnValue:
        loop: asyncio.AbstractEventLoop = current_app.config['reducer_loop']
        reducer: Reducer = current_app.config['reducer_obj']

        async def run_push() -> None:
            reducer.log('error', 'admin.test_push', 'test push message')

        asyncio.run_coroutine_threadsafe(run_push(), loop)

        flash('已发送测试消息', 'success')
        return redirect(url_for('.index'))

    @expose('/regenerate_token')
    def regenerate_token(self) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']

        with reducer.SqlSession() as session:
            users: List[store.UserStore] = session.execute(select(store.UserStore)).scalars().all()
            for u in users:
                u.token = utils.sign_token(u.id)
            session.commit()
            flash(f'已重新生成 {len(users)} 个 token，请手动重启 reducer 和所有 worker', 'success')

        return redirect(url_for('.index'))

    @expose('/check_dyn_flag/<ch_key>/<int:uid>')
    def check_dyn_flag(self, ch_key: str, uid: int) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        ch = reducer._game.challenges.chall_by_key.get(ch_key, None)
        u = reducer._game.users.user_by_id.get(uid, None)

        if ch is None:
            return '题目不存在'
        if u is None:
            return '用户不存在'

        ret = f'TOKEN = {u._store.token!r}\n\nFLAGS = {[f.correct_flag(u) for f in ch.flags]}'

        resp = make_response(ret, 200)
        resp.mimetype = 'text/plain'
        return resp

class ViewBase(sqla.ModelView): # type: ignore
    form_base_class = SecureForm
    list_template = 'list.html'
    edit_template = 'edit_ace.html'
    create_template = 'create_ace.html'
    details_modal_template = 'details_break_word.html'

    page_size = 100
    can_set_page_size = True

    @staticmethod
    def emit_event(event_type: glitter.EventType, id: Optional[int] = None) -> None:
        loop: asyncio.AbstractEventLoop = current_app.config['reducer_loop']
        reducer: Reducer = current_app.config['reducer_obj']

        async def task() -> None:
            reducer.state_counter += 1
            event = glitter.Event(event_type, reducer.state_counter, id or 0)
            await reducer.emit_event(event)

        asyncio.run_coroutine_threadsafe(task(), loop)

    def after_model_touched(self, model: Any) -> None:
        pass

    def after_model_change(self, form: Any, model: Any, is_created: bool) -> None:
        self.after_model_touched(model)

    def after_model_delete(self, model: Any) -> None:
        self.after_model_touched(model)

class AnnouncementView(ViewBase):
    column_formatters = {
        'timestamp_s': fields.timestamp_s_formatter,
        'content_template': macro('in_pre'),
    }
    form_overrides = {
        'timestamp_s': fields.TimestampSField,
        'content_template': fields.MarkdownField,
    }
    column_descriptions = {
        'content_template': '支持 Markdown 和 Jinja2 模板（group: Optional[str]、tick: int）',
    }
    column_default_sort = ('id', True)

    def after_model_touched(self, model: store.AnnouncementStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_ANNOUNCEMENT, model.id)

class ChallengeView(ViewBase):
    list_template = 'list_challenge.html'

    column_exclude_list = ['desc_template', 'chall_metadata']
    column_default_sort = 'sorting_index'
    column_formatters = {
        'actions': lambda _v, _c, model, _n: '；'.join([f'[{a["type"]}] {a["name"]}' for a in model.actions]),
        'flags': lambda _v, _c, model, _n: '；'.join([f'[{f["base_score"]}pt] {f["name"]}' for f in model.flags]),
    }
    column_descriptions = {
        'effective_after': '题目从该 Tick 编号后对选手可见',
        'key': '题目唯一 ID，将会显示在 URL 中，比赛中不要随意修改，否则会导致已有提交失效',
        'sorting_index': '越小越靠前',
        'desc_template': '支持 Markdown 和 Jinja2 模板（group: Optional[str]、tick: int）',
        'chall_metadata': '比赛结束后会向选手展示命题人',
        'actions': '题面底部展示的动作列表',
    }
    form_overrides = {
        'desc_template': fields.MarkdownField,
        'chall_metadata': fields.JsonField,
        'actions': fields.ActionsField,
        'flags': fields.FlagsField,
    }
    form_choices = {
        'category': [(x, x) for x in store.ChallengeStore.CAT_COLORS.keys()],
    }

    @staticmethod
    def _export_chall(ch: store.ChallengeStore) -> Dict[str, Any]:
        return {
            'effective_after': ch.effective_after,

            'key': ch.key,
            'title': ch.title,
            'category': ch.category,
            'sorting_index': ch.sorting_index,
            'desc_template': ch.desc_template,

            'chall_metadata': ch.chall_metadata,
            'actions': ch.actions,
            'flags': ch.flags,
        }

    @staticmethod
    def _import_chall(data: Dict[str, Any], ch: store.ChallengeStore) -> None:
        ch.effective_after = data['effective_after']

        ch.key = data['key']
        ch.title = data['title']
        ch.category = data['category']
        ch.sorting_index = data['sorting_index']
        ch.desc_template = data['desc_template']

        ch.chall_metadata = data['chall_metadata']
        ch.actions = data['actions']
        ch.flags = data['flags']

    @expose('/import_json', methods=['GET', 'POST'])
    def import_json(self) -> ResponseReturnValue:
        url = request.args.get('url', self.get_url('.index_view'))

        if request.method=='GET':
            return self.render('import_challenge.html')
        else:
            reducer: Reducer = current_app.config['reducer_obj']
            challs = json.loads(request.form['imported_data'])

            touched_ids = []

            with reducer.SqlSession() as session:
                n_added = 0
                n_modified = 0
                for ch_data in challs:
                    chall: Optional[store.ChallengeStore] = session.execute(
                        select(store.ChallengeStore).where(store.ChallengeStore.key==ch_data['key'])
                    ).scalar()

                    if chall is None:
                        chall = store.ChallengeStore()
                        session.add(chall)
                        n_added += 1
                    else:
                        n_modified += 1

                    self._import_chall(ch_data, chall)
                    session.flush()
                    touched_ids.append(chall.id)

                session.commit()

            for ch_id in touched_ids:
                self.emit_event(glitter.EventType.UPDATE_CHALLENGE, ch_id)

            flash(f'成功增加 {n_added} 个题目、修改 {n_modified} 个题目', 'success')

            return redirect(url)

    @action('export', 'Export JSON')
    def action_export(self, ch_ids: List[int]) -> ResponseReturnValue:
        reducer: Reducer = current_app.config['reducer_obj']
        challs = [self._export_chall(reducer._game.challenges.chall_by_id[int(ch_id)]._store) for ch_id in ch_ids]

        resp = make_response(json.dumps(challs, indent=1, ensure_ascii=False), 200)
        resp.mimetype = 'text/plain'
        return resp

    def create_form(self, **kwargs: Any) -> Form:
        form = super().create_form(**kwargs)
        if form.chall_metadata.data is None:
            form.chall_metadata.data = json.loads(store.ChallengeStore.METADATA_SNIPPET)
        return form


    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：增删题目或者修改 flags、effective_after 字段会重算排行榜', 'warning')

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_CHALLENGE, model.id)

class GamePolicyView(ViewBase):
    column_descriptions = {
        'effective_after': '策略从该 Tick 编号后生效',
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改赛程配置会重算排行榜', 'warning')

    def after_model_touched(self, model: store.GamePolicyStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_GAME_POLICY)

class LogView(ViewBase):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True

    column_default_sort = ('id', True)
    column_searchable_list = ['module', 'message']
    column_filters = ['level', 'process', 'module', 'message']

    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'level': macro('status_label'),
        'message': macro('in_pre'),
    }

def _flag_match_formatter(_view: Any, _context: Any, model: store.SubmissionStore, _name: str) -> str:
    reducer: Reducer = current_app.config['reducer_obj']
    sub = reducer._game.submissions.get(model.id, None)

    if sub is None:
        return '???'

    if sub.matched_flag:
        return f'{sub.matched_flag.name or "FLAG"} (+{sub.gained_score()})'
    elif sub.duplicate_submission:
        return '(duplicate)'
    else:
        return ''

def _flag_override_formatter(_view: Any, _context: Any, model: store.SubmissionStore, _name: str) -> str:
    ret = []
    if model.score_override_or_null is not None:
        ret.append(f'[={model.score_override_or_null}]')
    if model.precentage_override_or_null is not None:
        ret.append(f'[*{model.precentage_override_or_null}%]')

    return ' '.join(ret)

class SubmissionView(ViewBase):
    can_create = False
    can_delete = False

    column_list = ['id', 'timestamp_ms', 'user_id', 'user_.profile.nickname_or_null', 'user_.group', 'user_.login_key', 'challenge_key', 'flag', 'matched_flag', 'override']

    column_display_pk = True
    column_searchable_list = ['id']
    column_filters = ['user_id', 'challenge_key']
    column_default_sort = ('id', True)

    column_labels = {
        'user_.profile.nickname_or_null': 'User Nickname',
        'user_.group': 'User Group',
        'user_.login_key': 'User Login Key',
    }
    column_descriptions = {
        'score_override_or_null': '将选手分数覆盖为此值，与 score_override_or_null 同时存在时分数以此为准',
        'precentage_override_or_null': '将选手分数乘以此百分比，设置后此提交将不计入通过人数',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'matched_flag': _flag_match_formatter,
        'override': _flag_override_formatter,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改历史提交会重算排行榜', 'warning')

    def after_model_touched(self, model: store.ChallengeStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_SUBMISSION, model.id)

class TriggerView(ViewBase):
    column_descriptions = {
        'tick': f'Tick 编号，应为自然数且随时间递增，排行榜横轴范围是 Tick {Trigger.TRIGGER_BOARD_BEGIN} ~ {Trigger.TRIGGER_BOARD_END}',
        'name': '将在前端展示，半角分号表示换行',
    }
    column_formatters = {
        'timestamp_s': fields.timestamp_s_formatter,
    }
    form_overrides = {
        'timestamp_s': fields.TimestampSField,
    }
    column_default_sort = 'timestamp_s'

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改赛程配置会重算排行榜', 'warning')

    def after_model_touched(self, model: store.TriggerStore) -> None:
        self.emit_event(glitter.EventType.RELOAD_TRIGGER)

class UserProfileView(ViewBase):
    can_create = False
    can_delete = False

    column_display_pk = True

    column_searchable_list = ['id']
    column_filters = ['user_id', 'qq_or_null', 'comment_or_null']
    column_default_sort = ('id', True)

    column_descriptions = {
        'timestamp_ms': '用户保存此信息的时间',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
    }

    def after_model_touched(self, model: store.UserProfileStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.user_id)

def _user_oauth_info_formatter(_view: Any, _context: Any, model: store.UserStore, _name: str) -> str:
    return model.format_login_properties()

def _user_game_status_formatter(_view: Any, _context: Any, model: store.UserStore, _name: str) -> str:
    reducer: Reducer = current_app.config['reducer_obj']
    user = reducer._game.users.user_by_id.get(model.id, None)

    if user is None:
        return '???'

    res = user.check_play_game()
    if res is None:
        return 'OK'
    else:
        return res[1]

def _user_board_info_formatter(_view: Any, _context: Any, model: store.UserStore, _name: str) -> str:
    reducer: Reducer = current_app.config['reducer_obj']
    user = reducer._game.users.user_by_id.get(model.id, None)

    if user is None:
        return '???'

    return f'{user.tot_score} [{", ".join(user._store.badges())}]'

class UserView(ViewBase):
    can_create = False
    can_delete = False
    can_export = True
    can_view_details = True
    details_modal = True

    column_list = ['id', 'profile.nickname_or_null', 'group', 'profile.qq_or_null', 'login_key', 'oauth_info', 'game_status', 'board_info']
    column_exclude_list = ['token', 'auth_token', 'login_properties']
    column_display_pk = True

    column_searchable_list = ['id']
    column_filters = ['group', 'terms_agreed', 'login_key']
    column_labels = {
        'profile.nickname_or_null': 'Nickname',
        'profile.qq_or_null': 'QQ',
    }
    form_choices = {
        'group': list(store.UserStore.GROUPS.items()),
    }

    column_descriptions = {
        'login_key': 'OAuth Provider 提供的唯一 ID，用于判断用户是注册还是登录',
        'login_properties': 'OAuth Provider 提供的用户信息',
        'timestamp_ms': '注册时间',
        'enabled': '是否允许登录',
        'token': '在前端展示，平台本身不使用',
        'auth_token': '登录凭据，登录后会存在 Cookie 里',
    }
    column_formatters = {
        'timestamp_ms': fields.timestamp_ms_formatter,
        'oauth_info': _user_oauth_info_formatter,
        'game_status': _user_game_status_formatter,
        'board_info': _user_board_info_formatter,
    }
    column_formatters_detail = {
        'login_properties': lambda _v, _c, model, _n: (
            Markup('<samp style="white-space: pre-wrap">%s</samp>') % json.dumps(model.login_properties, indent=4, ensure_ascii=False)
        ),
        'timestamp_ms': fields.timestamp_ms_formatter,
    }
    form_overrides = {
        'login_properties': fields.JsonField,
        'timestamp_ms': fields.TimestampMsField,
    }

    def on_form_prefill(self, *args: Any, **kwargs: Any) -> None:
        flash('警告：修改 group 字段会重算排行榜', 'warning')

    def after_model_touched(self, model: store.UserStore) -> None:
        self.emit_event(glitter.EventType.UPDATE_USER, model.id)

VIEWS = {
    'AnnouncementStore': AnnouncementView,
    'ChallengeStore': ChallengeView,
    'GamePolicyStore': GamePolicyView,
    'LogStore': LogView,
    'SubmissionStore': SubmissionView,
    'TriggerStore': TriggerView,
    'UserStore': UserView,
    'UserProfileStore': UserProfileView,
}

# fix crlf and encoding on windows
class FileAdmin(fileadmin.BaseFileAdmin):  # type: ignore
    class FixingCrlfFileStorage(fileadmin.LocalFileStorage):  # type: ignore
        def write_file(self, path: str, content: str) -> int:
            with open(path, 'w', encoding='utf-8') as f:
                return f.write(content.replace('\r\n', '\n'))

    def __init__(self, base_path: str, *args: Any, **kwargs: Any) -> None:
        storage = self.FixingCrlfFileStorage(base_path)
        super().__init__(*args, storage=storage, **kwargs)

class TemplateView(FileAdmin):
    can_upload = True
    can_mkdir = False
    can_delete = False
    can_delete_dirs = False
    can_rename = False
    editable_extensions = ['md']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.MarkdownField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm

class WriteupView(FileAdmin):
    can_upload = False
    can_mkdir = False
    can_delete = False
    can_delete_dirs = False
    can_rename = False
    can_download = True
    editable_extensions = ['json']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.JsonTextField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm

class FilesView(FileAdmin):
    can_upload = True
    can_mkdir = True
    can_delete = True
    can_delete_dirs = True
    can_rename = True
    can_download = True
    editable_extensions = ['py']

    form_base_class = SecureForm
    edit_template = 'edit_ace.html'

    def get_edit_form(self) -> Type[Any]:
        class EditForm(self.form_base_class): # type: ignore
            content = fields.PythonField(lazy_gettext('Content'), (validators.InputRequired(),))

        return EditForm