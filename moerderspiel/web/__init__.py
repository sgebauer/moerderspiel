import datetime
from functools import wraps

import flask
import jwt
from flask import Flask, render_template, send_from_directory, request, url_for, redirect, flash, abort, session
from flask_sqlalchemy import SQLAlchemy

from moerderspiel.db import Base, Game, Mission, Circle, Player, NotificationAddressType
from moerderspiel import config, graph, pdf, notification
from moerderspiel.game import GameService, GameError
from moerderspiel.web.forms import AddPlayerForm, CreateGameForm, RecordMurderForm, GameMasterLoginForm, AddCircleForm

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


def needs_gamemaster_authentication(f):
    @wraps(f)
    def decorated_function(service: GameService, **kwargs):
        if service.game.id in (session.get('gamemaster_authenticated') or []):
            return f(service=service, **kwargs)
        else:
            return redirect(url_for('game', game_id=service.game.id, _anchor=GameMasterLoginForm.form_id))

    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def index():
    create_game_form = CreateGameForm()

    if request.method == 'POST' and request.form['form'] == CreateGameForm.form_id:
        create_game_form = CreateGameForm(request.form)
        if create_game_form.validate():
            try:
                service = GameService.create_new_game(
                    session=db.session,
                    id=create_game_form.game_id.data,
                    title=create_game_form.title.data,
                    gamemaster_password=create_game_form.password.data,
                )
                db.session.commit()
                session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [service.game.id]
                return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')

    return render_template('index.html.j2',
                           create_game_form=create_game_form)


@app.route('/game/<game_id>', methods=['GET', 'POST'])
@with_game_service
def game(service: GameService):
    add_player_form = AddPlayerForm(request.form)
    record_murder_form = RecordMurderForm(service.game, request.form)
    gamemaster_login_form = GameMasterLoginForm(request.form)

    if request.method == 'POST' and request.form['form'] == add_player_form.form_id:
        if add_player_form.validate():
            try:
                player = service.add_player(name=add_player_form.name.data, group=add_player_form.group.data)
                for circle in service.game.circles:
                    service.add_player_to_circle(player, circle)
                db.session.commit()

                if add_player_form.email.data:
                    send_confirmation_message(player, NotificationAddressType.email, add_player_form.email.data)

                flash('Spieler eingetragen', 'success')
                return redirect(url_for('game', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == record_murder_form.form_id:
        if record_murder_form.validate():
            try:
                service.record_murder(killer=record_murder_form.killer.data,
                                      victim=record_murder_form.victim.data,
                                      circle=record_murder_form.circle.data,
                                      when=record_murder_form.when.data,
                                      code=record_murder_form.mission_code.data,
                                      reason=record_murder_form.description.data)
                db.session.commit()
                flash('Mord eingetragen', 'success')
                return redirect(url_for('game', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == gamemaster_login_form.form_id:
        if gamemaster_login_form.validate():
            try:
                if service.check_gamemaster_password(gamemaster_login_form.password.data):
                    session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [service.game.id]
                    return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
                else:
                    flash('Falsches Passwort', 'error')
            except GameError as e:
                flash(str(e), 'error')

    return render_template('game.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game),
                           mass_murderers=Mission.mass_murderers_by_game(service.game),
                           add_player_form=add_player_form,
                           record_murder_form=record_murder_form,
                           gamemaster_login_form=gamemaster_login_form)


@app.route('/gamemaster/<game_id>', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def gamemaster(service: GameService):
    add_circle_form = AddCircleForm(request.form)

    if request.method == 'POST' and 'action' in request.form:
        try:
            if request.form['action'] == 'start-game':
                service.start_game()
            elif request.form['action'] == 'end-game':
                service.end_game()
            elif request.form['action'] == 'kick-player':
                service.kick_player(request.form['player'], datetime.datetime.now(), "Spieler wurde gekickt")
            elif request.form['action'] == 'resend-player-missions':
                service.send_mission_update(request.form['player'])
            db.session.commit()
            return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
        except GameError as e:
            flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == add_circle_form.form_id:
        if add_circle_form.validate():
            try:
                circle = service.add_circle(add_circle_form.name.data, set=add_circle_form.set.data)
                missions = sum((c.missions for c in Circle.by_game_and_set(service.game, circle.set)), start=[])
                for player in set(m.victim for m in missions):
                    service.add_player_to_circle(player, circle)
                db.session.commit()
                return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')

    return render_template('gamemaster.html.j2',
                           game=service.game,
                           add_circle_form=add_circle_form)


@app.get('/game/<game_id>/graph.svg')
@with_game_service
def game_graph(service: GameService):
    if 'circle' in request.args:
        circles = [service.get_circle(c) for c in request.args.getlist('circle')]
    else:
        circles = Circle.by_game(service.game)

    return flask.send_file(graph.generate_circles_graph(circles, show_original_owners=service.game.ended))


@app.get('/game/<game_id>/wall')
@with_game_service
def game_wall(service: GameService):
    return render_template('wall.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game))


@app.get('/game/<game_id>/missions.pdf')
@with_game_service
@needs_gamemaster_authentication
def game_missions(service: GameService):
    return flask.send_file(pdf.generate_game_mission_sheets(service.game))


@app.get('/game/<game_id>/missions/<player_name>.pdf')
@with_game_service
@needs_gamemaster_authentication  # For now, until player authentication is implemented
def player_missions(service: GameService, player_name: str):
    return flask.send_file(pdf.generate_mission_sheets(service.get_current_missions(player_name)))


@app.get('/game')
def game_redirect():
    if 'id' not in request.args:
        return redirect(url_for('/'))
    else:
        return redirect(url_for('game', game_id=request.args['id']))


@app.route('/css/<path:path>')
def css(path):
    return send_from_directory('static/css', path)


@app.route('/img/<path:path>')
def img(path):
    return send_from_directory('static/img', path)


@app.get('/confirm_address')
def confirm_address():
    if 'token' not in request.args:
        abort(400)

    data = jwt.decode(request.args['token'], key=app.secret_key, algorithms=["HS256"])
    service = GameService(Game.by_id(db.session, data['game']))
    service.add_notification_address(data['player'], NotificationAddressType[data['type']], data['address'])
    db.session.commit()

    flash('Benachrichtigungs-Adresse bestätigt', 'success')
    return redirect(url_for('game', game_id=service.game.id))


def send_confirmation_message(player: Player, address_type: NotificationAddressType, address: str):
    data = dict(game=player.game_id, player=player.name, type=address_type, address=address)
    token = jwt.encode(data, app.secret_key, algorithm="HS256")

    notification.email.send_confirmation_message(
        address=address,
        url=url_for('confirm_address', _external=True, token=token),
        game_title=player.game.title)
