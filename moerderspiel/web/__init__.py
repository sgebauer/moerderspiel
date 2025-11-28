import datetime
from functools import wraps

import flask
import jwt
from flask import Flask, render_template, send_from_directory, request, url_for, redirect, flash, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import TimeoutError, OperationalError
from werkzeug.exceptions import HTTPException, RequestTimeout, InternalServerError

from moerderspiel.db import Base, Game, Mission, Circle, Player, NotificationAddressType
from moerderspiel import config, graph, pdf, notification
from moerderspiel.game import GameService, GameError, NoSuchPlayerError
from moerderspiel.web.errors import ERROR_DESCRIPTIONS
from moerderspiel.web.forms import AddPlayerForm, PlayerLoginForm, CreateGameForm, RecordMurderForm, \
    GameMasterLoginForm, AddCircleForm

app = Flask(__name__)
app.config.from_prefixed_env()
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
app.config["SECRET_KEY"] = config.SECRET_KEY
db = SQLAlchemy(app, model_class=Base)
with app.app_context():
    db.create_all()


def with_game_service(f):
    @wraps(f)
    def decorated_function(game_id: str, **kwargs):
        kwargs['service'] = GameService(db.get_or_404(Game, game_id))
        return f(**kwargs)

    return decorated_function


def with_player(f):
    @wraps(f)
    def decorated_function(service: GameService, player_name: str, **kwargs):
        try:
            kwargs['player'] = service.get_player(player_name)
        except NoSuchPlayerError:
            return 404
        return f(service=service, **kwargs)

    return decorated_function


def needs_gamemaster_authentication(f):
    @wraps(f)
    def decorated_function(service: GameService, **kwargs):
        if service.game.id in (session.get('gamemaster_authenticated') or []):
            return f(service=service, **kwargs)
        else:
            return redirect(url_for('game', game_id=service.game.id, _anchor=GameMasterLoginForm.form_id))

    return decorated_function


def needs_player_authentication(f):
    @wraps(f)
    def decorated_function(player: Player, **kwargs):
        if player.id in (session.get('player_authenticated') or []):
            return f(player=player, **kwargs)
        else:
            return redirect(url_for('game', game_id=player.game.id, _anchor=PlayerLoginForm.form_id))

    return decorated_function


def store_player_authentication(player: Player):
    session['player_authenticated'] = (session.get('player_authenticated') or []) + [player.id]


def store_gamemaster_authentication(game: Game):
    session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [game.id]


@app.route('/', methods=['GET', 'POST'])
def index():
    def on_create_game(form):
        service = GameService.create_new_game(
            session=db.session,
            id=form.game_id.data,
            title=form.title.data,
            gamemaster_password=form.password.data
        )
        db.session.commit()
        store_gamemaster_authentication(service.game)
        return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))

    forms = {
        CreateGameForm.form_id: CreateGameForm(db.session, formdata=request.form, on_submit=on_create_game)
    }

    result = None
    if request.method == 'GET' and 'game-id' in request.args:
        result = redirect(url_for('game', game_id=request.args['game-id']))
    if request.method == 'POST' and 'form' in request.form:
        result = forms[request.form['form']].handle_form_submit()

    return result or render_template('index.html.j2', forms=forms.values())

@app.route('/-/css/<path:path>')
def css(path):
    return send_from_directory('static/css', path)


@app.route('/-/img/<path:path>')
def img(path):
    return send_from_directory('static/img', path)


@app.route('/-/assets/<path:path>')
def assets(path):
    return send_from_directory('static/assets', path)


@app.get('/-/confirm_address')
def confirm_address():
    if 'token' not in request.args:
        abort(400)

    data = jwt.decode(request.args['token'], key=app.secret_key, algorithms=["HS256"])
    service = GameService(Game.by_id(db.session, data['game']))
    service.add_notification_address(data['player'], NotificationAddressType[data['type']], data['address'])
    db.session.commit()

    flash('Benachrichtigungs-Adresse bestätigt', 'success')
    return redirect(url_for('game', game_id=service.game.id))


@app.route('/<game_id>', methods=['GET', 'POST'])
@with_game_service
def game(service: GameService):
    def on_add_player(form: AddPlayerForm):
        if not form.email.data and not form.password.data:
            # TODO: Turn this into a validator, and make it configurable per game
            flash('Bitte gib eine E-Mail-Adresse oder ein Passwort an - Sonst kommst du später nicht an deine Aufträge!', 'error')
            return None

        player = service.add_player(name=form.name.data, group=form.group.data, player_password=form.password.data)
        db.session.commit()

        if form.email.data:
            send_confirmation_message(player, NotificationAddressType.email, form.email.data)

        store_player_authentication(player)
        return redirect(url_for('player', game_id=service.game.id, player_name=player.name, _anchor='top'))

    def on_record_murder(form: RecordMurderForm):
        service.record_murder(killer=form.killer.data,
                              victim=form.victim.data,
                              circle=form.circle.data,
                              when=form.when.data,
                              code=form.mission_code.data,
                              reason=form.description.data)
        db.session.commit()
        flash('Mord eingetragen', 'success')
        return redirect(url_for('game', game_id=service.game.id, _anchor='top'))

    def on_gamemaster_login(form: GameMasterLoginForm):
        store_gamemaster_authentication(service.game)
        return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))

    def on_player_login(form: PlayerLoginForm):
        player = service.get_player(form.name.data)
        store_player_authentication(player)
        return redirect(url_for('player', game_id=service.game.id, player_name=player.name, _anchor='top'))

    forms = {
        AddPlayerForm.form_id: AddPlayerForm(service, formdata=request.form, on_submit=on_add_player),
        RecordMurderForm.form_id: RecordMurderForm(service, formdata=request.form, on_submit=on_record_murder),
        GameMasterLoginForm.form_id: GameMasterLoginForm(service, formdata=request.form, on_submit=on_gamemaster_login),
        PlayerLoginForm.form_id: PlayerLoginForm(service, formdata=request.form, on_submit=on_player_login)
    }

    result = None
    if request.method == 'POST' and 'form' in request.form:
        result = forms[request.form['form']].handle_form_submit()

    return result or render_template('game.html.j2',
                                     game=service.game,
                                     completed_missions=Mission.completed_missions_in_game(service.game),
                                     mass_murderers=Mission.mass_murderers_by_game(service.game),
                                     forms=forms.values())


@app.route('/<game_id>/gamemaster', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def gamemaster(service: GameService):
    def on_add_circle(form):
        service.add_circle(form.name.data, set=form.set.data, players=None)
        db.session.commit()
        return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))

    forms = {
        AddCircleForm.form_id: AddCircleForm(service, formdata=request.form, on_submit=on_add_circle)
    }

    result = None
    if request.method == 'POST' and 'form' in request.form:
        result = forms[request.form['form']].handle_form_submit()
    elif request.method == 'POST' and 'action' in request.form:
        service.sanitize_game_data()
        db.session.commit()

        if request.form['action'] == 'start-game':
            service.start_game()
        elif request.form['action'] == 'end-game':
            service.end_game()
        elif request.form['action'] == 'delete-player':
            service.delete_player(request.form['player'])
        elif request.form['action'] == 'kick-player':
            service.kick_player(request.form['player'], datetime.datetime.now(), "Spieler wurde gekickt")
        elif request.form['action'] == 'resend-player-missions':
            service.send_mission_update(request.form['player'])
        elif request.form['action'] == 'delete-circle':
            service.delete_circle(request.form['circle'])
        db.session.commit()
        result = redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))

    return result or render_template('gamemaster.html.j2', game=service.game, forms=forms.values())


@app.route('/<game_id>/player/<player_name>')
@with_game_service
@with_player
@needs_player_authentication
def player(service: GameService, player: Player):
    if request.method == 'POST' and 'action' in request.form:
        if request.form['action'] == 'resend-player-missions':
            service.send_mission_update(player)

    return render_template('player.html.j2',
                           player=player,
                           game=service.game,
                           open_missions=Mission.achievable_missions_by_current_owner(player)
                           if service.game.started else None)


@app.get('/<game_id>/graph.svg')
@with_game_service
def game_graph(service: GameService):
    if 'circle' in request.args:
        circles = [service.get_circle(c) for c in request.args.getlist('circle')]
    else:
        circles = Circle.by_game(service.game)

    return flask.send_file(graph.generate_circles_graph(circles,
                                                        show_original_owners=service.game.ended,
                                                        show_isolated_players=service.game.ended))


@app.get('/<game_id>/wall')
@with_game_service
def game_wall(service: GameService):
    return render_template('wall.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game))


@app.get('/<game_id>/gamemaster/missions.pdf')
@with_game_service
@needs_gamemaster_authentication
def game_missions(service: GameService):
    return flask.send_file(pdf.generate_game_mission_sheets(service.game))


@app.get('/<game_id>/player/<player_name>/missions.pdf')
@with_game_service
@with_player
@needs_player_authentication
def player_missions(service: GameService, player: Player):
    return flask.send_file(pdf.generate_mission_sheets(service.get_current_missions(player)))


def send_confirmation_message(player: Player, address_type: NotificationAddressType, address: str):
    data = dict(game=player.game_id, player=player.name, type=address_type, address=address)
    token = jwt.encode(data, app.secret_key, algorithm="HS256")

    notification.email.send_confirmation_message(
        address=address,
        url=url_for('confirm_address', _external=True, token=token),
        game_title=player.game.title)


@app.errorhandler(HTTPException)
def serve_error_page(e: HTTPException):
    if e.code in ERROR_DESCRIPTIONS:
        return render_template('error.html.j2',
                               error_code=e.code,
                               error_title=ERROR_DESCRIPTIONS[e.code]['title'],
                               error_message=ERROR_DESCRIPTIONS[e.code]['message']), e.code

    return e


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, TimeoutError):
        return serve_error_page(RequestTimeout())
    elif isinstance(e, OperationalError) and 'timeout' in str(e).lower():
        return serve_error_page(RequestTimeout())

    app.logger.exception("Unhandled exception", exc_info=e)
    return serve_error_page(InternalServerError())
