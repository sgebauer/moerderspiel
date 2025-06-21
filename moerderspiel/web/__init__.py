import datetime
from functools import wraps

import flask
import jwt
import markdown
from flask import Flask, render_template, send_from_directory, request, url_for, redirect, flash, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import TimeoutError, OperationalError

from moerderspiel.db import Base, Game, Mission, Circle, Player, NotificationAddressType
from moerderspiel import config, graph, pdf, notification
from moerderspiel.game import GameService, GameError
from moerderspiel.player import PlayerService
from moerderspiel.web.forms import AddPlayerForm, PlayerLoginForm, CreateGameForm, RecordMurderForm, \
    GameMasterLoginForm, AddCircleForm, ChooseCirclesetForm, EditRulesForm, AdminLoginForm, ChangeGamemasterPasswordForm, UpdatePlayerEmailForm


app = Flask(__name__)
app.config.from_prefixed_env()
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
app.config["SECRET_KEY"] = config.SECRET_KEY
db = SQLAlchemy(app, model_class=Base)
with app.app_context():
    db.create_all()


@app.context_processor
def inject_config():
    return dict(config=config)


def with_game_service(f):
    @wraps(f)
    def decorated_function(game_id: str, **kwargs):
        kwargs['service'] = GameService(db.get_or_404(Game, game_id))
        return f(**kwargs)

    return decorated_function


def with_player_service(f):
    @wraps(f)
    def decorated_function(player_id: str, **kwargs):
        kwargs['service'] = PlayerService(db.get_or_404(Player, player_id))
        return f(**kwargs)

    return decorated_function


def needs_gamemaster_authentication(f):
    @wraps(f)
    def decorated_function(service: GameService, **kwargs):
        # Allow access if user is authenticated as gamemaster for this game OR as admin
        if (service.game.id in (session.get('gamemaster_authenticated') or []) or 
            (config.ADMIN_ENABLED and session.get('admin_authenticated'))):
            return f(service=service, **kwargs)
        else:
            return redirect(url_for('game', game_id=service.game.id, _anchor=GameMasterLoginForm.form_id))

    return decorated_function


def needs_player_authentication(f):
    @wraps(f)
    def decorated_function(service: PlayerService, **kwargs):
        if service.player.id in (session.get('player_authenticated') or []):
            return f(service=service, **kwargs)
        else:
            return redirect(url_for('game', game_id=service.player.game.id, _anchor=PlayerLoginForm.form_id))

    return decorated_function


def needs_admin_authentication(f):
    @wraps(f)
    def decorated_function(**kwargs):
        if not config.ADMIN_ENABLED:
            abort(404)  # Admin interface disabled
        if session.get('admin_authenticated'):
            return f(**kwargs)
        else:
            return redirect(url_for('admin_login'))

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
                session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [
                    service.game.id]
                return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')

    return render_template('index.html.j2',
                           create_game_form=create_game_form)


@app.route('/game/<game_id>', methods=['GET', 'POST'])
@with_game_service
def game(service: GameService):
    add_player_form = AddPlayerForm(service.game, request.form)
    record_murder_form = RecordMurderForm(service.game, request.form)
    gamemaster_login_form = GameMasterLoginForm(request.form)
    player_login_form = PlayerLoginForm(request.form)

    if request.method == 'POST' and request.form['form'] == add_player_form.form_id:
        if add_player_form.validate():
            try:
                if add_player_form.password.data:
                    player_login = service.add_player(
                        name=add_player_form.name.data,
                        group=add_player_form.group.data,
                        circleset_string='|'.join(add_player_form.circle_sets.data),
                        player_password=add_player_form.password.data)
                else:
                    player_login = service.add_player(
                        name=add_player_form.name.data,
                        group=add_player_form.group.data)

                circles = []
                if add_player_form.circle_sets.data:
                    for circle_set in add_player_form.circle_sets.data:
                        circles += Circle.by_game_and_set(service.game, circle_set)
                    circles = list(set(circles))
                else:
                    circles = service.game.circles

                for circle in circles:
                    service.add_player_to_circle(player_login, circle)
                db.session.commit()

                if add_player_form.email.data:
                    send_confirmation_message(player_login, NotificationAddressType.email, add_player_form.email.data)

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
                    session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [
                        service.game.id]
                    return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
                else:
                    flash('Falsches Passwort', 'error')
            except GameError as e:
                flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == player_login_form.form_id:
        if player_login_form.validate():
            try:
                if service.check_player_password(player_login_form.password.data, player_login_form.name.data):
                    player_login = service.get_player(player_login_form.name.data)
                    session['player_authenticated'] = (session.get('player_authenticated') or []) + [
                        player_login.id]
                    return redirect(
                        url_for('player', player_id=player_login.id, _anchor='top'))
                else:
                    flash('Falsches Passwort', 'error')
            except GameError as e:
                flash(str(e), 'error')

    return render_template('game.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game, exclude_kicks=True),
                           mass_murderers=Mission.mass_murderers_by_game(service.game),
                           completed_missions_circleset=completed_missions_per_circleset(service.game),
                           mass_murderers_circleset=mass_murderer_per_circleset(service.game),
                           add_player_form=add_player_form,
                           record_murder_form=record_murder_form,
                           gamemaster_login_form=gamemaster_login_form,
                           player_login_form=player_login_form)


@app.route('/gamemaster/<game_id>', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def gamemaster(service: GameService):
    add_circle_form = AddCircleForm(request.form)

    if request.method == 'POST' and 'action' in request.form:
        try:
            service.sanitize_game_data()
            db.session.commit()

            if request.form['action'] == 'start-game':
                service.start_game()
            elif request.form['action'] == 'end-game':
                service.end_game()
            elif request.form['action'] == 'delete-player':
                service.delete_player(request.form['player'])
            elif request.form['action'] == 'kick-player':
                # Get kick preview info first
                kick_info = service.get_kick_preview(request.form['player'])
                # Store in session for the confirmation modal
                session['pending_kick'] = {
                    'player_name': request.form['player'],
                    'kick_info': kick_info
                }
                # Return JSON response for AJAX handling
                return flask.jsonify({
                    'action': 'show_kick_modal',
                    'kick_info': kick_info
                })
            elif request.form['action'] == 'confirm-kick-player':
                # Actually kick the player
                player_name = request.form['player']
                service.kick_player(player_name, datetime.datetime.now(), "Spieler wurde gekickt")
                # Clear pending kick from session
                session.pop('pending_kick', None)
            elif request.form['action'] == 'resend-player-missions':
                service.send_mission_update(request.form['player'])
            elif request.form['action'] == 'delete-circle':
                service.delete_circle(request.form['circle'])
            db.session.commit()
            return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
        except GameError as e:
            flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == add_circle_form.form_id:
        if add_circle_form.validate():
            try:
                service.add_circle(add_circle_form.name.data, set=add_circle_form.set.data, players=None)
                db.session.commit()
                return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')

    return render_template('gamemaster.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game, exclude_kicks=True),
                           add_circle_form=add_circle_form,
                           is_admin_access=(config.ADMIN_ENABLED and session.get('admin_authenticated') and 
                                          service.game.id not in (session.get('gamemaster_authenticated') or [])))


@app.route('/player/<player_id>', methods=['GET', 'POST'])
@with_player_service
@needs_player_authentication
def player(service: PlayerService):
    circle_set_form = ChooseCirclesetForm(service.player.game, request.form)
    email_form = UpdatePlayerEmailForm(request.form)

    if request.method == 'POST' and request.form['form'] == circle_set_form.form_id:
        try:
            in_circles = []
            for circle_set in circle_set_form.circle_sets.data:
                in_circles += Circle.by_game_and_set(service.player.game, circle_set)
            in_circles = list(set(in_circles))

            out_circles = [c for c in service.player.game.circles if c not in in_circles]


            for circle in in_circles:
                service.add_player_to_circle(circle)
            for circle in out_circles:
                service.remove_player_from_circle(circle)
            service.player.circleset_string = '|'.join(c.name for c in in_circles)
            db.session.commit()

            flash('Teilnahme an Sets geändert', 'success')
        except GameError as e:
            flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == email_form.form_id:
        if email_form.validate():
            try:
                # Remove existing email notification addresses
                existing_email_addresses = [addr for addr in service.player.notification_addresses 
                                          if addr.type == NotificationAddressType.email]
                for addr in existing_email_addresses:
                    db.session.delete(addr)
                
                # Add new email address if provided
                if email_form.email.data:
                    send_confirmation_message(service.player, NotificationAddressType.email, email_form.email.data)
                    flash('E-Mail-Adresse aktualisiert. Bitte prüfen Sie Ihre E-Mails für die Bestätigung.', 'success')
                else:
                    flash('E-Mail-Benachrichtigungen wurden deaktiviert.', 'success')
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f'Fehler beim Aktualisieren der E-Mail-Adresse: {str(e)}', 'error')
        else:
            for field, errors in email_form.errors.items():
                for error in errors:
                    flash(f'E-Mail: {error}', 'error')

    # Get current email address for form population
    current_email = None
    for addr in service.player.notification_addresses:
        if addr.type == NotificationAddressType.email and addr.active:
            current_email = addr.address
            break
    
    # Populate email form with current address
    if request.method == 'GET' and current_email:
        email_form.email.data = current_email

    return render_template('player.html.j2',
                           circle_set_form=circle_set_form,
                           email_form=email_form,
                           player=service.player,
                           game=service.player.game,
                           player_circle_set=service.player.circle_sets,
                           completed_missions=Mission.completed_missions_in_game_by_owner(service.player.game, service.player, exclude_kicks=True),
                           open_missions=service.get_current_missions())


@app.route('/gamemaster/<game_id>/player/<player_name>', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def gamemaster_player_view(service: GameService, player_name: str):
    """Gamemaster view of a specific player's page"""
    try:
        player = service.get_player(player_name)
        player_service = PlayerService(player)
        
        circle_set_form = ChooseCirclesetForm(player.game, request.form)
        email_form = UpdatePlayerEmailForm(request.form)

        if request.method == 'POST' and request.form['form'] == circle_set_form.form_id:
            try:
                in_circles = []
                for circle_set in circle_set_form.circle_sets.data:
                    in_circles += Circle.by_game_and_set(player.game, circle_set)
                in_circles = list(set(in_circles))

                out_circles = [c for c in player.game.circles if c not in in_circles]

                for circle in in_circles:
                    player_service.add_player_to_circle(circle)
                for circle in out_circles:
                    player_service.remove_player_from_circle(circle)
                player.circleset_string = '|'.join(c.name for c in in_circles)
                db.session.commit()

                flash('Teilnahme an Sets geändert', 'success')
            except GameError as e:
                flash(str(e), 'error')
        elif request.method == 'POST' and request.form['form'] == email_form.form_id:
            if email_form.validate():
                try:
                    # Remove existing email notification addresses
                    existing_email_addresses = [addr for addr in player.notification_addresses 
                                              if addr.type == NotificationAddressType.email]
                    for addr in existing_email_addresses:
                        db.session.delete(addr)
                    
                    # Add new email address if provided
                    if email_form.email.data:
                        send_confirmation_message(player, NotificationAddressType.email, email_form.email.data)
                        flash('E-Mail-Adresse aktualisiert. Bitte prüfen Sie Ihre E-Mails für die Bestätigung.', 'success')
                    else:
                        flash('E-Mail-Benachrichtigungen wurden deaktiviert.', 'success')
                    
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    flash(f'Fehler beim Aktualisieren der E-Mail-Adresse: {str(e)}', 'error')
            else:
                for field, errors in email_form.errors.items():
                    for error in errors:
                        flash(f'E-Mail: {error}', 'error')

        # Get current email address for form population
        current_email = None
        for addr in player.notification_addresses:
            if addr.type == NotificationAddressType.email and addr.active:
                current_email = addr.address
                break
        
        # Populate email form with current address
        if request.method == 'GET' and current_email:
            email_form.email.data = current_email

        return render_template('player.html.j2',
                               circle_set_form=circle_set_form,
                               email_form=email_form,
                               player=player,
                               game=player.game,
                               player_circle_set=player.circle_sets,
                               completed_missions=Mission.completed_missions_in_game_by_owner(player.game, player, exclude_kicks=True),
                               open_missions=player_service.get_current_missions(),
                               is_gamemaster_view=True)
    except Exception as e:
        flash(f'Spieler "{player_name}" nicht gefunden', 'error')
        return redirect(url_for('gamemaster', game_id=service.game.id))


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
                           completed_missions_circleset=completed_missions_per_circleset(service.game))


@app.get('/game/<game_id>/missions.pdf')
@with_game_service
@needs_gamemaster_authentication
def game_missions(service: GameService):
    return flask.send_file(pdf.generate_game_mission_sheets(service.game))


@app.route('/rules/<game_id>', methods=['GET'])
@with_game_service
def game_rules(service: GameService):
    import markdown
    
    rules_text = service.game.rules or "Noch kein Regeltext hinzugefügt."
    rules_html = markdown.markdown(rules_text)
    
    return render_template('rules.html.j2',
                           game=service.game,
                           rules_html=rules_html)


@app.route('/gamemaster/<game_id>/edit-rules', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def edit_rules(service: GameService):
    if request.method == 'POST':
        edit_rules_form = EditRulesForm(service.game, formdata=request.form)
    else:
        edit_rules_form = EditRulesForm(service.game)
    
    if request.method == 'POST':
        if request.form.get('form') == edit_rules_form.form_id:
            if edit_rules_form.validate():
                try:
                    service.update_rules(edit_rules_form.rules.data)
                    db.session.commit()
                    flash('Spielregeln aktualisiert', 'success')
                    return redirect(url_for('gamemaster', game_id=service.game.id))
                except Exception as e:
                    print(f"[ERR]  Error saving rules: {str(e)}")
                    flash(f'Fehler beim Speichern der Regeln: {str(e)}', 'error')
            else:
                # Validierungsfehler anzeigen
                for field, errors in edit_rules_form.errors.items():
                    for error in errors:
                        flash(f'Fehler in {field}: {error}', 'error')
        else:
            print('[WARN] Invalid form submission detected. Form ID does not match expected value.')
            flash('Ungültige Anfrage', 'error')
    
    return render_template('edit_rules.html.j2',
                           game=service.game,
                           edit_rules_form=edit_rules_form)


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

def completed_missions_per_circleset(game: Game) -> dict :
    ret = {}
    circles = Circle.by_game(game)
    for circle in circles:
        # Exclude gamemaster kicks from public mission display
        circle_missions = Mission.completed_missions_in_game_by_circle(game, circle, exclude_kicks=True)
        if circle.set and circle.set in ret:
            ret[circle.set] = ret[circle.set] + circle_missions
        else:
            ret[circle.set] = circle_missions
    return ret

def mass_murderer_per_circleset(game: Game) -> dict : #TODO hier stimmt was ned, da is leer wenn nciht sein sollte
    ret = {}
    circles = Circle.by_game(game)
    for circle in circles:
        if circle.set in ret:
            ret[circle.set] = ret[circle.set] + Mission.mass_murderers_by_circle(game, circle)
        else:
            ret[circle.set] = Mission.mass_murderers_by_circle(game, circle)
    return ret


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if not config.ADMIN_ENABLED:
        abort(404)  # Admin interface disabled
        
    admin_form = AdminLoginForm(request.form)
    
    if request.method == 'POST' and admin_form.validate():
        if admin_form.password.data == config.ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            flash('Admin-Anmeldung erfolgreich', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Falsches Admin-Passwort', 'error')
    
    return render_template('admin_login.html.j2', admin_form=admin_form)


@app.route('/admin')
@needs_admin_authentication
def admin_dashboard():
    """Main admin dashboard"""
    games = db.session.scalars(db.select(Game)).all()
    return render_template('admin_dashboard.html.j2', games=games)


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    flash('Admin-Abmeldung erfolgreich', 'success')
    return redirect(url_for('index'))


@app.route('/admin/game/<game_id>/delete', methods=['POST'])
@needs_admin_authentication
def admin_delete_game(game_id: str):
    """Delete a game - requires confirmation"""
    if request.form.get('confirm') != 'DELETE':
        flash('Spiel-Löschung erfordert Bestätigung', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        game = db.get_or_404(Game, game_id)
        db.session.delete(game)
        db.session.commit()
        flash(f'Spiel "{game.title}" wurde erfolgreich gelöscht', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Löschen des Spiels: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/game/<game_id>/force-end', methods=['POST'])
@needs_admin_authentication
def admin_force_end_game(game_id: str):
    """Force end a game"""
    try:
        service = GameService(db.get_or_404(Game, game_id))
        service.end_game()
        db.session.commit()
        flash(f'Spiel "{service.game.title}" wurde beendet', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler beim Beenden des Spiels: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/game/<game_id>/view')
@needs_admin_authentication
def admin_view_game(game_id: str):
    """View detailed game information in admin interface"""
    game = db.get_or_404(Game, game_id)
    service = GameService(game)
    change_password_form = ChangeGamemasterPasswordForm()
    
    return render_template('admin_game_detail.html.j2', 
                          game=game,
                          service=service,
                          completed_missions=Mission.completed_missions_in_game(game),
                          mass_murderers=Mission.mass_murderers_by_game(game),
                          change_password_form=change_password_form)


@app.route('/admin/game/<game_id>/change-gamemaster-password', methods=['POST'])
@needs_admin_authentication
def admin_change_gamemaster_password(game_id: str):
    """Change gamemaster password for a game"""
    game = db.get_or_404(Game, game_id)
    form = ChangeGamemasterPasswordForm(request.form)
    
    if form.validate():
        try:
            from werkzeug.security import generate_password_hash
            game.gamemaster_password = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash(f'Gamemaster-Passwort für Spiel "{game.title}" wurde erfolgreich geändert', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Ändern des Passworts: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('admin_view_game', game_id=game_id))


@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 errors with a custom error page."""
    return render_template('404.html.j2'), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 errors with a custom error page."""
    return render_template('error.html.j2', 
                         error_code=500,
                         error_title="Interner Serverfehler",
                         error_message="Es ist ein unerwarteter Fehler aufgetreten. Das Spiel wurde unterbrochen!"), 500


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors with a custom error page."""
    return render_template('error.html.j2',
                         error_code=403,
                         error_title="Zugriff verweigert",
                         error_message="Sie haben keine Berechtigung, auf diese Seite zuzugreifen. Nur echte Mörder dürfen hier rein!"), 403


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 errors with a custom error page."""
    return render_template('error.html.j2',
                         error_code=400,
                         error_title="Ungültige Anfrage",
                         error_message="Die Anfrage konnte nicht verarbeitet werden. Bitte überprüfen Sie Ihre Eingabe."), 400


@app.errorhandler(408)
def request_timeout(error):
    """Handle 408 request timeout errors."""
    return render_template('error.html.j2',
                         error_code=408,
                         error_title="Zeitüberschreitung",
                         error_message="Die Anfrage hat zu lange gedauert. Auch ein perfekter Mord braucht Zeit, aber nicht so viel!"), 408


@app.errorhandler(504)
def gateway_timeout(error):
    """Handle 504 gateway timeout errors."""
    return render_template('error.html.j2',
                         error_code=504,
                         error_title="Gateway Zeitüberschreitung",
                         error_message="Der Server antwortet nicht rechtzeitig. Das Spiel scheint pausiert zu sein."), 504


@app.errorhandler(502)
def bad_gateway(error):
    """Handle 502 bad gateway errors."""
    return render_template('error.html.j2',
                         error_code=502,
                         error_title="Gateway Fehler",
                         error_message="Der Server ist vorübergehend nicht erreichbar. Bitte versuchen Sie es später erneut."), 502


@app.errorhandler(503)
def service_unavailable(error):
    """Handle 503 service unavailable errors."""
    return render_template('error.html.j2',
                         error_code=503,
                         error_title="Dienst nicht verfügbar",
                         error_message="Der Server ist überlastet oder wartungsbedingt nicht verfügbar. Das Spiel ist temporär pausiert."), 503


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle any unhandled exceptions."""
    # Check for database timeout errors
    if isinstance(error, (TimeoutError, OperationalError)):
        if 'timeout' in str(error).lower():
            return render_template('error.html.j2',
                                 error_code=408,
                                 error_title="Datenbank Zeitüberschreitung",
                                 error_message="Die Datenbank antwortet nicht rechtzeitig. Das Spiel läuft gerade sehr langsam."), 408
    
    # Check if it's a timeout-related exception
    if 'timeout' in str(error).lower() or 'timed out' in str(error).lower():
        return render_template('error.html.j2',
                             error_code=408,
                             error_title="Zeitüberschreitung",
                             error_message="Die Verbindung wurde wegen Zeitüberschreitung unterbrochen. Versuchen Sie es erneut."), 408
    
    # For development, you might want to see the actual error
    # In production, log the error and show a generic message
    app.logger.error(f"Unhandled exception: {error}")
    
    return render_template('error.html.j2',
                         error_code=500,
                         error_title="Unerwarteter Fehler",
                         error_message="Es ist ein unerwarteter Fehler aufgetreten. Das Spiel wurde unterbrochen!"), 500


@app.errorhandler(TimeoutError)
def handle_timeout_error(error):
    """Handle SQLAlchemy timeout errors specifically."""
    return render_template('error.html.j2',
                         error_code=408,
                         error_title="Datenbank Zeitüberschreitung",
                         error_message="Die Datenbank-Verbindung ist zeitüberschritten. Bitte versuchen Sie es erneut."), 408


@app.errorhandler(OperationalError)
def handle_operational_error(error):
    """Handle SQLAlchemy operational errors that might include timeouts."""
    if 'timeout' in str(error).lower():
        return render_template('error.html.j2',
                             error_code=408,
                             error_title="Datenbank Zeitüberschreitung",
                             error_message="Die Datenbank antwortet nicht rechtzeitig. Bitte haben Sie etwas Geduld."), 408
    else:
        app.logger.error(f"Database operational error: {error}")
        return render_template('error.html.j2',
                             error_code=503,
                             error_title="Datenbankfehler",
                             error_message="Es gibt ein Problem mit der Datenbank. Bitte versuchen Sie es später erneut."), 503


@app.get('/gamemaster/<game_id>/player/<player_name>/target_jobs')
@with_game_service
@needs_gamemaster_authentication
def player_target_jobs(service: GameService, player_name: str):
    """Get all jobs targeting a specific player"""
    try:
        player = service.get_player(player_name)
        target_jobs = []
        
        for mission in player.victim_missions:
            # Handle current owner safely (might be None for completed missions)
            current_owner_name = None
            if service.game.started and not mission.completed:
                try:
                    current_owner_name = mission.current_owner.name
                except AttributeError:
                    # current_owner might be None in some edge cases
                    current_owner_name = None
            
            # Handle killer name properly
            killer_name = None
            if mission.completed:
                # Mission is completed
                if mission.killer:
                    killer_name = mission.killer.name
                else:
                    # Completed mission with no killer means kicked/admin action
                    killer_name = "Gekickt/Admin"
            # If mission is not completed, killer_name stays None (will show as "-" in frontend)
            
            target_jobs.append({
                'mission_id': mission.position,
                'circle_name': mission.circle.name,
                'circle_set': mission.circle.set,
                'killer_name': killer_name,
                'mission_code': mission.code if service.game.started else None,
                'completed': mission.completion_date is not None,
                'completed_at': mission.completion_date.isoformat() if mission.completion_date else None,
                'current_owner': current_owner_name
            })
        
        return flask.jsonify(target_jobs)
    except GameError as e:
        return flask.jsonify({'error': str(e)}), 400


@app.get('/gamemaster/<game_id>/player/<player_name>/kick_preview')
@with_game_service
@needs_gamemaster_authentication
def kick_preview(service: GameService, player_name: str):
    """Get preview of what happens when a player is kicked"""
    try:
        kick_info = service.get_kick_preview(player_name)
        return flask.jsonify(kick_info)
    except GameError as e:
        return flask.jsonify({'error': str(e)}), 400


